// Step 2 of the flow (upload plan → concept images → AI builds the 3D tour): generate interior
// design concept images with Gemini from the floor plan, the client's references and the brief.
// The images are saved under public/concepts/<id>/ and returned with base64 so the design-tour
// step can pass them to Claude as references.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import type { CafeScene } from "@/types/cafescene";

export const maxDuration = 300;

// Tried in order; the free tier has no quota for the pro image model, so flash comes first unless
// GEMINI_IMAGE_MODEL says otherwise.
const CANDIDATES = Array.from(
  new Set([process.env.GEMINI_IMAGE_MODEL, "gemini-3.1-flash-image", "gemini-2.5-flash-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image"].filter(Boolean) as string[]),
);
const ENDPOINT = (model: string) => `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`;

type MediaType = "image/jpeg" | "image/png" | "image/webp" | "image/gif";
interface ImageIn {
  data: string;
  mediaType: MediaType;
  name?: string;
}
interface Body {
  projectName?: string;
  brief?: string;
  count?: number;
  planImages?: ImageIn[];
  references?: ImageIn[];
  scene?: CafeScene;
}

interface GeminiPart {
  text?: string;
  inlineData?: { mimeType: string; data: string };
}
interface GeminiResponse {
  candidates?: { content?: { parts?: GeminiPart[] }; finishReason?: string }[];
  error?: { message?: string; status?: string; code?: number };
  promptFeedback?: { blockReason?: string };
}

const VIEWS: { key: string; label: string; what: string }[] = [
  { key: "counter", label: "Service counter & back bar", what: "the service counter run with the espresso station, grinders, pastry / grab-and-go displays and the till, and the back bar shelving behind it" },
  { key: "dining", label: "Dining room", what: "the main seating area: tables, chairs, banquette, pendant lighting and the feature wall" },
  { key: "entrance", label: "Entrance & terrace", what: "the street-facing entrance with the glazed shopfront, signage and the outdoor terrace seating with umbrellas and planters" },
  { key: "retail", label: "Order & retail wall", what: "the self-order kiosks, menu screens and the retail wall with beans, cups and brewing gear" },
];

const isMedia = (m: unknown): m is MediaType => m === "image/jpeg" || m === "image/png" || m === "image/webp" || m === "image/gif";

function roomSummary(scene?: CafeScene): string {
  if (!scene) return "";
  const rooms = scene.rooms.map((r) => `${r.name} (${r.category.replace(/_/g, " ")})`).join(", ");
  const legend = scene.legend.slice(0, 20).map((l) => l.name).join(", ");
  return `Rooms on the plan: ${rooms}.${legend ? ` Equipment list: ${legend}.` : ""}`;
}

async function generateOne(key: string, model: string, parts: GeminiPart[]): Promise<{ mimeType: string; data: string } | { error: string; quota?: boolean }> {
  const res = await fetch(ENDPOINT(model), {
    method: "POST",
    headers: { "x-goog-api-key": key, "content-type": "application/json" },
    body: JSON.stringify({
      contents: [{ role: "user", parts }],
      generationConfig: { responseModalities: ["IMAGE", "TEXT"], imageConfig: { aspectRatio: "16:9" } },
    }),
  });
  const d = (await res.json().catch(() => ({}))) as GeminiResponse;
  if (!res.ok || d.error) {
    const msg = d.error?.message || res.statusText;
    // Free-tier projects have a hard 0 quota for every image model: no point trying the others.
    if ((d.error?.code ?? res.status) === 429 && /free[_ ]tier/i.test(msg)) return { error: "free-tier", quota: true };
    return { error: `Gemini ${model}: ${msg.split("\n")[0].slice(0, 200)} (${d.error?.code ?? res.status})` };
  }
  if (d.promptFeedback?.blockReason) return { error: `Gemini blocked the prompt (${d.promptFeedback.blockReason}).` };
  const img = d.candidates?.[0]?.content?.parts?.find((p) => p.inlineData?.data)?.inlineData;
  if (!img) return { error: `Gemini ${model} returned no image (${d.candidates?.[0]?.finishReason ?? "no candidates"}).` };
  return { mimeType: img.mimeType, data: img.data };
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Body;
  const key = process.env.GEMINI_API_KEY;
  if (!key) {
    return Response.json({ error: "Concept-image generation needs GEMINI_API_KEY in webapp/.env.local.", notConfigured: true }, { status: 501 });
  }
  const n = Math.min(Math.max(body.count ?? 3, 1), VIEWS.length);
  const name = (body.projectName || "a specialty coffee shop").trim();
  const brief = (body.brief || "warm contemporary materials: oak, terrazzo, brushed brass, cream plaster, black accents").trim().slice(0, 3000);
  const plans = (body.planImages ?? []).filter((i) => i?.data && isMedia(i.mediaType)).slice(0, 2);
  const refs = (body.references ?? []).filter((i) => i?.data && isMedia(i.mediaType)).slice(0, 4);

  const id = `${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${crypto.randomUUID().slice(0, 6)}`;
  const outDir = path.join(process.cwd(), "public", "concepts", id);
  await mkdir(outDir, { recursive: true });

  const images: { url: string; label: string; data: string; mediaType: string }[] = [];
  const errors: string[] = [];
  const modelsUsed = new Set<string>();

  for (let i = 0; i < n; i++) {
    const view = VIEWS[i];
    const parts: GeminiPart[] = [];
    plans.forEach((p, k) => {
      parts.push({ text: `Floor plan page ${k + 1} of the café (for layout, proportions and where each zone sits):` });
      parts.push({ inlineData: { mimeType: p.mediaType, data: p.data } });
    });
    refs.forEach((r, k) => {
      parts.push({ text: `Interior reference ${k + 1} (match this material palette, furniture language and mood):` });
      parts.push({ inlineData: { mimeType: r.mediaType, data: r.data } });
    });
    parts.push({
      text:
        `Create an interior design concept visualization of ${name}: ${view.what}. ` +
        `Design brief: ${brief} ${roomSummary(body.scene)} ` +
        `Lay the space out as the floor plan shows. Photorealistic architectural rendering, eye-level camera, ` +
        `soft daylight mixed with warm 2700K interior lighting, realistic materials and reflections, no people, ` +
        `no text overlays or captions in the image.`,
    });

    let r: Awaited<ReturnType<typeof generateOne>> = { error: "no model" };
    let usedModel = "";
    for (const m of CANDIDATES) {
      r = await generateOne(key, m, parts);
      if (!("error" in r)) {
        usedModel = m;
        break;
      }
      if (r.quota) {
        return Response.json(
          {
            error:
              "Your Gemini project is on the free tier, which has no image-generation quota (every image model answers with limit 0). " +
              "Enable billing for the Google project behind GEMINI_API_KEY (AI Studio → Plan & billing), or use a key from a billed project, then retry. " +
              "You can still attach your own reference images and run the 3D design.",
            quota: true,
            images: [],
          },
          { status: 402 },
        );
      }
      errors.push(`${view.label}: ${r.error}`);
    }
    if ("error" in r) continue;
    if (usedModel) modelsUsed.add(usedModel);
    const ext = r.mimeType.includes("jpeg") ? "jpg" : r.mimeType.includes("webp") ? "webp" : "png";
    const file = `view-${i + 1}-${view.key}.${ext}`;
    await writeFile(path.join(outDir, file), Buffer.from(r.data, "base64"));
    images.push({ url: `/concepts/${id}/${file}`, label: view.label, data: r.data, mediaType: r.mimeType });
  }

  if (!images.length) return Response.json({ error: errors.join(" · ") || "Gemini returned no images.", images: [] }, { status: 502 });
  // only report errors that mattered (a model that failed before another succeeded is noise)
  return Response.json({ id, model: [...modelsUsed].join(","), images, errors: images.length === n ? [] : errors });
}
