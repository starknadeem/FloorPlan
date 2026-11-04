// AI design-tour route — Claude designs the café and writes a complete walkable three.js tour
// (self-contained HTML) from the floor plan, the parsed CafeScene and interior references.
// Streams NDJSON progress while the model writes, then saves the page under public/designs/<id>/.
//   {type:"progress", chars, label, elapsedMs}
//   {type:"done", id, url, usage, chars}
//   {type:"error", error, partialUrl?}
// GET lists previously generated designs.

import Anthropic from "@anthropic-ai/sdk";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import type { CafeScene } from "@/types/cafescene";
import { DESIGN_TOUR_SYSTEM, buildUserText, compactScene, loadExemplar } from "@/lib/design-tour/prompt";

export const maxDuration = 300;

type Effort = "low" | "medium" | "high" | "xhigh" | "max";
const MODEL = process.env.DESIGN_TOUR_MODEL || "claude-opus-5-5";
// "high": xhigh spent a whole 64k budget deliberating and never wrote the page. 128k is the model's
// output ceiling; thinking tokens count against it, so leave room for the ~30k-token document.
const EFFORT = (process.env.DESIGN_TOUR_EFFORT || "medium") as Effort; // "high" and "xhigh" both spent the entire output budget thinking and wrote nothing
const MAX_TOKENS = Number(process.env.DESIGN_TOUR_MAX_TOKENS || 128000);

type MediaType = "image/jpeg" | "image/png" | "image/webp" | "image/gif";
interface ImageIn {
  data: string; // base64, no data: prefix
  mediaType: MediaType;
  name?: string;
}
interface Body {
  scene?: CafeScene;
  planImages?: ImageIn[];
  references?: ImageIn[];
  referenceUrls?: string[];
  brief?: string;
  projectName?: string;
}

interface DesignMeta {
  id: string;
  projectName: string;
  brief: string;
  createdAt: string;
  model: string;
  effort: string;
  stopReason: string | null;
  chars: number;
  usage?: { input_tokens: number; output_tokens: number; cache_read_input_tokens?: number | null; cache_creation_input_tokens?: number | null };
  url: string;
  complete: boolean;
}

const isMedia = (m: unknown): m is MediaType => m === "image/jpeg" || m === "image/png" || m === "image/webp" || m === "image/gif";

/** Pull the HTML document out of the model text (tolerates fences / stray prose). */
function extractHtml(text: string): { html: string; complete: boolean } {
  let t = text;
  const fence = t.match(/```(?:html)?\s*([\s\S]*?)```/i);
  if (fence && fence[1].includes("<html")) t = fence[1];
  const start = (() => {
    const a = t.search(/<!doctype html/i);
    if (a >= 0) return a;
    const b = t.search(/<html[\s>]/i);
    return b >= 0 ? b : 0;
  })();
  const endIdx = t.toLowerCase().lastIndexOf("</html>");
  const complete = endIdx > start;
  const html = complete ? t.slice(start, endIdx + 7) : t.slice(start);
  return { html: html.trim(), complete };
}

function designsDir() {
  return path.join(process.cwd(), "public", "designs");
}

export async function GET() {
  const dir = designsDir();
  let ids: string[] = [];
  try {
    ids = await readdir(dir);
  } catch {
    return Response.json({ designs: [] });
  }
  const metas: DesignMeta[] = [];
  for (const id of ids) {
    try {
      metas.push(JSON.parse(await readFile(path.join(dir, id, "meta.json"), "utf8")) as DesignMeta);
    } catch {
      /* skip */
    }
  }
  metas.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  return Response.json({ designs: metas });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Body;
  const planImages = (body.planImages ?? []).filter((i) => i?.data && isMedia(i.mediaType));
  const references = (body.references ?? []).filter((i) => i?.data && isMedia(i.mediaType));
  const referenceUrls = (body.referenceUrls ?? []).filter((u) => typeof u === "string" && /^https?:\/\//.test(u));
  const scene = body.scene && typeof body.scene === "object" ? body.scene : undefined;
  if (!scene && !planImages.length) {
    return Response.json({ error: "Provide a parsed scene and/or floor plan image(s)." }, { status: 400 });
  }
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    return Response.json({ error: "ANTHROPIC_API_KEY is not set in webapp/.env.local." }, { status: 501 });
  }
  const projectName = (body.projectName || scene?.project?.name || "Café").trim();
  const brief = (body.brief || "").slice(0, 6000);

  const id = `${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${crypto.randomUUID().slice(0, 6)}`;
  const outDir = path.join(designsDir(), id);
  const url = `/designs/${id}/index.html`;

  const exemplar = await loadExemplar();
  const system: Anthropic.Beta.BetaTextBlockParam[] = [
    { type: "text", text: DESIGN_TOUR_SYSTEM },
    {
      type: "text",
      text:
        "REFERENCE IMPLEMENTATION — a finished tour for a different café, produced for this same product. Match its architecture (texture factory, materials, geometry helpers, lighting, hotspots, walking/collision/tour engine, map, UI) and its level of finish. Do NOT reuse its geometry, dimensions, copy, stop names or brand: the new café is the client's plan.\n\n" +
        exemplar,
      cache_control: { type: "ephemeral" },
    },
  ];

  const content: Anthropic.Beta.BetaContentBlockParam[] = [];
  planImages.forEach((img, i) => {
    content.push({ type: "text", text: `Floor plan page ${i + 1}${img.name ? ` (${img.name})` : ""}:` });
    content.push({ type: "image", source: { type: "base64", media_type: img.mediaType, data: img.data } });
  });
  let refIdx = 0;
  for (const img of references) {
    refIdx++;
    content.push({ type: "text", text: `Interior reference ${refIdx}${img.name ? ` (${img.name})` : ""}:` });
    content.push({ type: "image", source: { type: "base64", media_type: img.mediaType, data: img.data } });
  }
  for (const u of referenceUrls) {
    refIdx++;
    content.push({ type: "text", text: `Interior reference ${refIdx}:` });
    content.push({ type: "image", source: { type: "url", url: u } });
  }
  content.push({
    type: "text",
    text: buildUserText({ projectName, brief, sceneJson: scene ? compactScene(scene) : undefined, hasPlanImages: planImages.length > 0, refCount: refIdx }),
  });

  const client = new Anthropic({ timeout: 30 * 60 * 1000, maxRetries: 1 });
  const t0 = Date.now();

  const stream = new ReadableStream({
    async start(controller) {
      const enc = new TextEncoder();
      let closed = false;
      const send = (obj: unknown) => {
        if (closed) return;
        try {
          controller.enqueue(enc.encode(JSON.stringify(obj) + "\n"));
        } catch {
          closed = true;
        }
      };
      const labelFor = (chars: number) =>
        chars < 2500 ? "Designing the concept…" : chars < 18000 ? "Building shell, materials and lighting…" : chars < 45000 ? "Furnishing: counters, displays, seating, retail…" : "Wiring the tour: stops, map, controls…";

      let text = "";
      let lastSent = 0;
      let thinking = "";
      send({ type: "progress", chars: 0, label: "Reading the plan…", elapsedMs: 0 });

      const msgStream = client.beta.messages.stream({
        model: MODEL,
        max_tokens: MAX_TOKENS,
        betas: ["server-side-fallback-2026-07-01"],
        fallbacks: "default",
        system,
        // summarized thinking streams while the model plans, so the client sees live design notes
        thinking: { type: "adaptive", display: "summarized" },
        output_config: { effort: EFFORT },
        messages: [{ role: "user", content }],
      });
      const onAbort = () => msgStream.abort();
      req.signal?.addEventListener("abort", onAbort);

      // Heartbeat: planning can run for minutes before any code streams; keep the response body
      // alive (Node fetch times out a silent body after 5 min) and surface the latest design note.
      const heartbeat = setInterval(() => {
        const note = thinking.trim().split(/\n+/).filter(Boolean).pop() ?? "";
        send({
          type: "progress",
          chars: text.length,
          label: text.length ? labelFor(text.length) : note ? `Designing: ${note.slice(-140)}` : "Designing the concept…",
          elapsedMs: Date.now() - t0,
        });
      }, 4000);

      try {
        msgStream.on("thinking", (delta: string) => {
          thinking += delta;
          if (thinking.length > 4000) thinking = thinking.slice(-2000);
        });
        msgStream.on("text", (delta: string) => {
          text += delta;
          if (text.length - lastSent >= 1500) {
            lastSent = text.length;
            send({ type: "progress", chars: text.length, label: labelFor(text.length), elapsedMs: Date.now() - t0 });
          }
        });
        const final = await msgStream.finalMessage();
        const fullText = final.content.filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text").map((b) => b.text).join("");
        if (fullText.length > text.length) text = fullText;

        const usage = {
          input_tokens: final.usage.input_tokens,
          output_tokens: final.usage.output_tokens,
          cache_read_input_tokens: final.usage.cache_read_input_tokens ?? null,
          cache_creation_input_tokens: final.usage.cache_creation_input_tokens ?? null,
        };

        if (final.stop_reason === "refusal") {
          send({ type: "error", error: `The model declined this request${final.stop_details?.explanation ? `: ${final.stop_details.explanation}` : "."}` });
          return;
        }

        const { html, complete } = extractHtml(text);
        await mkdir(outDir, { recursive: true });
        await writeFile(path.join(outDir, "index.html"), html, "utf8");
        const meta: DesignMeta = {
          id,
          projectName,
          brief,
          createdAt: new Date().toISOString(),
          model: final.model,
          effort: EFFORT,
          stopReason: final.stop_reason,
          chars: html.length,
          usage,
          url,
          complete: complete && final.stop_reason !== "max_tokens",
        };
        await writeFile(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2), "utf8");

        if (final.stop_reason === "max_tokens" || !complete) {
          send({ type: "error", error: `The model ran out of room before finishing (stop_reason ${final.stop_reason}). The partial page was saved — raise DESIGN_TOUR_MAX_TOKENS and try again.`, partialUrl: url });
          return;
        }
        send({ type: "done", id, url, usage, chars: html.length, elapsedMs: Date.now() - t0, model: final.model });
      } catch (e) {
        let msg = e instanceof Error ? e.message : "Design generation failed";
        if (e instanceof Anthropic.AuthenticationError) msg = "Anthropic API key rejected. Check ANTHROPIC_API_KEY in webapp/.env.local.";
        else if (e instanceof Anthropic.RateLimitError) msg = "Rate limited by the Anthropic API. Wait a minute and try again.";
        else if (e instanceof Anthropic.APIError) msg = `Anthropic API error ${e.status}: ${e.message}`;
        send({ type: "error", error: msg });
      } finally {
        clearInterval(heartbeat);
        req.signal?.removeEventListener("abort", onAbort);
        closed = true;
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      }
    },
  });

  return new Response(stream, {
    headers: { "content-type": "application/x-ndjson; charset=utf-8", "cache-control": "no-store", "x-accel-buffering": "no" },
  });
}
