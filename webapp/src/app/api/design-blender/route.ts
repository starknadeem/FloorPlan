// AI → Blender route. Claude designs the interior as design.py (on top of blender/cafe_kit.py),
// then the server either (a) pushes it into the user's open Blender through the MCP addon socket
// (mode "live"), or (b) runs Blender headless to render stills and/or a 360° tour (mode "stills" |
// "panos" | "both"). Streams NDJSON:
//   {type:"progress", phase:"design"|"build"|"render", label, percent?, elapsedMs}
//   {type:"done", id, designUrl, stills:[{url,label}], tour?:{baseUrl, stops}, live?:string}
//   {type:"error", error, designUrl?}
// GET lists previous Blender designs.

import Anthropic from "@anthropic-ai/sdk";
import { spawn } from "node:child_process";
import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import net from "node:net";
import type { CafeScene } from "@/types/cafescene";
import { DESIGN_BLENDER_SYSTEM, buildBlenderUserText, loadKitAndExemplar } from "@/lib/design-blender/prompt";
import { LAYOUTS, directionById, pickDirection } from "@/lib/design-blender/directions";
import { startImageJob } from "@/lib/design-images/job";

export const maxDuration = 300;

type Effort = "low" | "medium" | "high" | "xhigh" | "max";
const MODEL = process.env.DESIGN_BLENDER_MODEL || process.env.DESIGN_TOUR_MODEL || "claude-opus-5-5";
const EFFORT = (process.env.DESIGN_BLENDER_EFFORT || "medium") as Effort; // a ~100-line script: "high" spent 32k tokens deliberating and wrote nothing
const MAX_TOKENS = Number(process.env.DESIGN_BLENDER_MAX_TOKENS || 128000); // thinking counts against this
const BLENDER_BIN = process.env.BLENDER_BIN || "blender";
const MCP_PORT = Number(process.env.BLENDER_MCP_PORT || 9876);

type MediaType = "image/jpeg" | "image/png" | "image/webp" | "image/gif";
interface ImageIn {
  data: string;
  mediaType: MediaType;
  name?: string;
}
interface Body {
  direction?: string;
  scene?: CafeScene;
  planImages?: ImageIn[];
  references?: ImageIn[];
  brief?: string;
  projectName?: string;
  mode?: "live" | "glb" | "stills" | "panos" | "both" | "design";
  samples?: number;
  res?: [number, number];
}
interface Meta {
  id: string;
  projectName: string;
  brief: string;
  createdAt: string;
  model: string;
  mode: string;
  designUrl: string;
  stills: { url: string; label: string }[];
  tour?: { baseUrl: string; stops: unknown[] };
  glbUrl?: string;
  sceneUrl?: string;
  complete: boolean;
  direction?: string;
  directionName?: string;
  seed?: number;
}

const isMedia = (m: unknown): m is MediaType => m === "image/jpeg" || m === "image/png" || m === "image/webp" || m === "image/gif";

function extractPython(text: string): string {
  const fence = text.match(/```(?:python|py)?\s*([\s\S]*?)```/i);
  let t = fence ? fence[1] : text;
  // drop any leading prose before the first kit line
  const i = t.search(/^\s*(K\s*=\s*Kit\(|#|from |import )/m);
  if (i > 0) t = t.slice(i);
  return t.trim() + "\n";
}

/** Direction ids of past designs, newest first. */
async function recentDirections(): Promise<string[]> {
  try {
    const ids = (await readdir(designsDir())).sort().reverse();
    const out: string[] = [];
    for (const id of ids.slice(0, 15)) {
      try {
        const m = JSON.parse(await readFile(path.join(designsDir(), id, "meta.json"), "utf8")) as Meta;
        if (m.direction) out.push(m.direction);
      } catch {
        /* folder without meta */
      }
    }
    return out;
  } catch {
    return [];
  }
}

function designsDir() {
  return path.join(process.cwd(), "public", "blender-designs");
}

/** Run Python in the user's live Blender through the MCP addon socket (raw JSON, one command). */
function runLive(code: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const sock = net.createConnection({ host: "127.0.0.1", port: MCP_PORT });
    let buf = "";
    const timer = setTimeout(() => {
      sock.destroy();
      reject(new Error("Blender did not answer within 4 minutes."));
    }, 240_000);
    sock.on("connect", () => sock.write(JSON.stringify({ type: "execute_code", params: { code } })));
    sock.on("data", (d) => {
      buf += d.toString("utf8");
      try {
        const r = JSON.parse(buf) as { status: string; result?: { result?: string }; message?: string };
        clearTimeout(timer);
        sock.end();
        if (r.status === "success") resolve(r.result?.result ?? "");
        else reject(new Error(r.message || "Blender returned an error"));
      } catch {
        /* incomplete JSON: keep reading */
      }
    });
    sock.on("error", (e) => {
      clearTimeout(timer);
      reject(new Error(`Could not reach Blender's MCP server on port ${MCP_PORT} (${e.message}). Open Blender and start the MCP server in the addon panel.`));
    });
  });
}

export async function GET() {
  const dir = designsDir();
  let ids: string[] = [];
  try {
    ids = await readdir(dir);
  } catch {
    return Response.json({ designs: [] });
  }
  const metas: Meta[] = [];
  for (const id of ids) {
    try {
      metas.push(JSON.parse(await readFile(path.join(dir, id, "meta.json"), "utf8")) as Meta);
    } catch {
      /* skip */
    }
  }
  metas.sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1));
  return Response.json({ designs: metas });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Body;
  const scene = body.scene && typeof body.scene === "object" ? body.scene : undefined;
  if (!scene) return Response.json({ error: "Provide a parsed scene." }, { status: 400 });
  if (!process.env.ANTHROPIC_API_KEY && !process.env.ANTHROPIC_AUTH_TOKEN) {
    return Response.json({ error: "ANTHROPIC_API_KEY is not set in webapp/.env.local." }, { status: 501 });
  }
  const planImages = (body.planImages ?? []).filter((i) => i?.data && isMedia(i.mediaType)).slice(0, 3);
  const references = (body.references ?? []).filter((i) => i?.data && isMedia(i.mediaType)).slice(0, 6);
  const projectName = (body.projectName || scene.project?.name || "Café").trim();
  const brief = (body.brief || "").slice(0, 6000);
  const mode = body.mode ?? "glb";
  const samples = Math.min(Math.max(body.samples ?? 64, 8), 512);
  const res = body.res ?? [1600, 900];

  const id = `${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${crypto.randomUUID().slice(0, 6)}`;
  const outDir = path.join(designsDir(), id);
  const designUrl = `/blender-designs/${id}/design.py`;
  const cwd = process.cwd();

  // every run: a fresh seed and a design direction that differs from the recent ones, so the same plan never repeats
  const recent = await recentDirections();
  const direction = directionById(body.direction) ?? pickDirection(recent);
  const layout = LAYOUTS[Math.floor(Math.random() * LAYOUTS.length)];
  const seed = Math.floor(Math.random() * 2 ** 31);

  const { kit, exemplar } = await loadKitAndExemplar();
  const system: Anthropic.Beta.BetaTextBlockParam[] = [
    { type: "text", text: DESIGN_BLENDER_SYSTEM },
    { type: "text", text: `=== cafe_kit.py (the API you build with) ===\n${kit}` },
    { type: "text", text: `=== EXEMPLAR design.py (API usage and level of care ONLY, for a different plan. Never reuse its concept, palette, materials or layout) ===\n${exemplar}`, cache_control: { type: "ephemeral" } },
  ];
  const content: Anthropic.Beta.BetaContentBlockParam[] = [];
  planImages.forEach((img, i) => {
    content.push({ type: "text", text: `Floor plan page ${i + 1}:` });
    content.push({ type: "image", source: { type: "base64", media_type: img.mediaType, data: img.data } });
  });
  references.forEach((img, i) => {
    content.push({ type: "text", text: `Interior reference ${i + 1}:` });
    content.push({ type: "image", source: { type: "base64", media_type: img.mediaType, data: img.data } });
  });
  content.push({ type: "text", text: buildBlenderUserText({ projectName, brief, scene, hasPlanImages: planImages.length > 0, refCount: references.length, direction, layout }) });

  const client = new Anthropic({ timeout: 20 * 60 * 1000, maxRetries: 1 });
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
      const progress = (phase: string, label: string, percent?: number) => send({ type: "progress", phase, label, percent, elapsedMs: Date.now() - t0 });

      let heartbeat: ReturnType<typeof setInterval> | null = null;
      try {
        // ---------- phase 1: Claude designs ----------
        progress("design", "Reading the plan and designing the interior…", 2);
        let thinking = "";
        let text = "";
        const msgStream = client.beta.messages.stream({
          model: MODEL,
          max_tokens: MAX_TOKENS,
          betas: ["server-side-fallback-2026-07-01"],
          fallbacks: "default",
          system,
          thinking: { type: "adaptive", display: "summarized" },
          output_config: { effort: EFFORT },
          messages: [{ role: "user", content }],
        });
        const onAbort = () => msgStream.abort();
        req.signal?.addEventListener("abort", onAbort);
        heartbeat = setInterval(() => {
          const note = thinking.trim().split(/\n+/).filter(Boolean).pop() ?? "";
          progress("design", text.length ? `Writing the build script… (${(text.length / 1024).toFixed(0)} KB)` : note ? `Designing: ${note.slice(-140)}` : "Designing the interior…", text.length ? 10 + Math.min(10, text.length / 800) : 5);
        }, 4000);
        msgStream.on("thinking", (d: string) => {
          thinking += d;
          if (thinking.length > 4000) thinking = thinking.slice(-2000);
        });
        msgStream.on("text", (d: string) => {
          text += d;
        });
        const final = await msgStream.finalMessage();
        req.signal?.removeEventListener("abort", onAbort);
        clearInterval(heartbeat);
        heartbeat = null;
        if (final.stop_reason === "refusal") {
          send({ type: "error", error: "The model declined this request." });
          return;
        }
        const full = final.content.filter((b): b is Anthropic.Beta.BetaTextBlock => b.type === "text").map((b) => b.text).join("");
        const code = extractPython(full || text);
        await mkdir(outDir, { recursive: true });
        await writeFile(path.join(outDir, "design.py"), code, "utf8");
        await writeFile(path.join(outDir, "scene.json"), JSON.stringify(scene), "utf8");
        const meta: Meta = { id, projectName, brief, createdAt: new Date().toISOString(), model: final.model, mode, designUrl, stills: [], complete: false, direction: direction.id, directionName: direction.name, seed };
        await writeFile(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2), "utf8");
        if (final.stop_reason === "max_tokens") {
          send({ type: "error", error: "The design script was cut off (max_tokens). Raise DESIGN_BLENDER_MAX_TOKENS.", designUrl });
          return;
        }
        progress("design", "Design written. Building in Blender…", 22);

        // ---------- phase 2: build ----------
        if (mode === "design") {
          meta.complete = true;
          await writeFile(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2), "utf8");
          send({ type: "done", id, designUrl, stills: [], elapsedMs: Date.now() - t0 });
          return;
        }
        if (mode === "live") {
          const kitDir = path.join(cwd, "blender");
          const live =
            `import sys, json, importlib\n` +
            `sys.path.insert(0, ${JSON.stringify(kitDir)})\n` +
            `import cafe_kit\nimportlib.reload(cafe_kit)\n` +
            `SCENE = json.load(open(${JSON.stringify(path.join(outDir, "scene.json"))}))\n` +
            `TEXTURES = ${JSON.stringify(path.join(cwd, "public", "textures"))}\n` +
            `Kit = cafe_kit.Kit\nimport math\nSEED = ${seed}\nSTYLE = ${JSON.stringify(direction.style)}\n` +
            `exec(compile(open(${JSON.stringify(path.join(outDir, "design.py"))}).read(), "design.py", "exec"))\n`;
          progress("build", "Building the café in your open Blender…", 40);
          const out = await runLive(live);
          meta.complete = true;
          await writeFile(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2), "utf8");
          send({ type: "done", id, designUrl, stills: [], live: out.trim().slice(-400), elapsedMs: Date.now() - t0 });
          return;
        }

        // headless render
        const args = [
          "--background", "--python", path.join(cwd, "blender", "run_design.py"), "--",
          "--scene", path.join(outDir, "scene.json"), "--design", path.join(outDir, "design.py"),
          "--out", outDir, "--mode", mode, "--samples", String(samples), "--res", `${res[0]}x${res[1]}`,
          "--textures", path.join(cwd, "public", "textures"),
          "--seed", String(seed), "--style", direction.style,
        ];
        const child = spawn(BLENDER_BIN, args, { cwd });
        let log = "";
        let buf = "";
        let total = 0, done = 0;
        const onLine = (line: string) => {
          log += line + "\n";
          if (log.length > 60000) log = log.slice(-40000);
          const m = line.match(/^(STILL|PANO)_TOTAL (\d+)/);
          if (m) {
            total += parseInt(m[2], 10);
            progress("render", `Rendering ${total} view${total === 1 ? "" : "s"} in Cycles…`, 30);
          }
          const d = line.match(/^(STILL|PANO)_DONE (\d+) (.*)$/);
          if (d) {
            done += 1;
            progress("render", `Rendered ${d[3]} (${done}/${total})`, 30 + Math.round((done / Math.max(1, total)) * 65));
          }
          if (line.startsWith("DESIGN_OK")) progress("build", mode === "glb" ? "Café built. Exporting the 3D model…" : "Café built. Rendering…", 28);
          if (line.startsWith("GLB_OK")) progress("build", "3D model exported.", mode === "glb" ? 90 : 30);
        };
        child.stdout.on("data", (d) => {
          buf += d.toString();
          const lines = buf.split("\n");
          buf = lines.pop() ?? "";
          lines.forEach(onLine);
        });
        child.stderr.on("data", (d) => {
          log += d.toString();
        });
        const onAbort2 = () => child.kill("SIGTERM");
        req.signal?.addEventListener("abort", onAbort2);
        const code2: number = await new Promise((resolve) => child.on("close", (c) => resolve(c ?? 1)));
        req.signal?.removeEventListener("abort", onAbort2);
        if (buf) onLine(buf);
        await writeFile(path.join(outDir, "blender.log"), log, "utf8");
        if (code2 !== 0 || !log.includes("RUN_OK")) {
          const tb = log.match(/Traceback[\s\S]{0,1500}/)?.[0] ?? log.slice(-800);
          send({ type: "error", error: `Blender failed (exit ${code2}).\n${tb}`, designUrl });
          return;
        }
        const result = JSON.parse(await readFile(path.join(outDir, "result.json"), "utf8")) as { stills: { label: string; image: string }[]; panos: { stops: unknown[] } | null; glb?: string | null };
        meta.stills = result.stills.map((s) => ({ url: `/blender-designs/${id}/${s.image}`, label: s.label }));
        if (result.panos) meta.tour = { baseUrl: `/blender-designs/${id}`, stops: result.panos.stops };
        if (result.glb) {
          meta.glbUrl = `/blender-designs/${id}/${result.glb}`;
          meta.sceneUrl = `/blender-designs/${id}/scene.json`;
        }
        meta.complete = true;
        await writeFile(path.join(outDir, "meta.json"), JSON.stringify(meta, null, 2), "utf8");
        // prepare the gallery in the background so its images are ready before anyone opens it (DESIGN_IMAGES_AUTO=0 turns this off)
        if (process.env.DESIGN_IMAGES_AUTO !== "0") await startImageJob(id).catch((e) => console.error("design-images:", e));
        send({ type: "done", id, designUrl, stills: meta.stills, tour: meta.tour, glbUrl: meta.glbUrl, sceneUrl: meta.sceneUrl, elapsedMs: Date.now() - t0 });
      } catch (e) {
        let msg = e instanceof Error ? e.message : "Blender design failed";
        if (e instanceof Anthropic.AuthenticationError) msg = "Anthropic API key rejected.";
        else if (e instanceof Anthropic.RateLimitError) msg = "Rate limited by the Anthropic API. Wait a minute and retry.";
        else if (e instanceof Anthropic.APIError) msg = `Anthropic API error ${e.status}: ${e.message}`;
        send({ type: "error", error: msg, designUrl });
      } finally {
        if (heartbeat) clearInterval(heartbeat);
        closed = true;
        try {
          controller.close();
        } catch {
          /* closed */
        }
      }
    },
  });
  return new Response(stream, { headers: { "content-type": "application/x-ndjson; charset=utf-8", "cache-control": "no-store", "x-accel-buffering": "no" } });
}
