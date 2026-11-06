// Two gates between the image model and the gallery. An AI image is published only if BOTH pass:
//   1. structureMatch: edges must line up with the render, which catches a changed camera or layout cheaply.
//   2. auditImages: a vision model lists anything added, removed or changed. Edges cannot tell a new plant from a shadow.
// Any doubt, including an unreadable audit answer, counts as not verified.

import Anthropic from "@anthropic-ai/sdk";
import sharp from "sharp";

const W = 384, H = 256;
const COLS = 4, ROWS = 3;
const AUDIT_MODEL = process.env.IMAGE_AUDIT_MODEL || "claude-sonnet-5-5";

async function edges(file: string): Promise<Float32Array> {
  const { data } = await sharp(file).resize(W, H, { fit: "fill" }).greyscale().blur(1.2).raw().toBuffer({ resolveWithObject: true });
  const out = new Float32Array(W * H);
  for (let y = 1; y < H - 1; y++) {
    for (let x = 1; x < W - 1; x++) {
      const i = y * W + x;
      out[i] = Math.hypot(data[i + 1] - data[i - 1], data[i + W] - data[i - W]);
    }
  }
  return out;
}

function pearson(a: Float32Array, b: Float32Array, x0: number, y0: number, x1: number, y1: number): number {
  let n = 0, sa = 0, sb = 0, saa = 0, sbb = 0, sab = 0;
  for (let y = y0; y < y1; y++) {
    for (let x = x0; x < x1; x++) {
      const i = y * W + x, u = a[i], v = b[i];
      n++; sa += u; sb += v; saa += u * u; sbb += v * v; sab += u * v;
    }
  }
  const den = Math.sqrt((n * saa - sa * sa) * (n * sbb - sb * sb));
  return den > 1e-6 ? (n * sab - sa * sb) / den : 1; // two empty tiles match
}

export interface StructureScore {
  overall: number;
  worstTile: number;
}

export async function structureMatch(renderFile: string, aiFile: string): Promise<StructureScore> {
  const [a, b] = await Promise.all([edges(renderFile), edges(aiFile)]);
  let worstTile = 1;
  for (let r = 0; r < ROWS; r++) {
    for (let c = 0; c < COLS; c++) {
      worstTile = Math.min(worstTile, pearson(a, b, Math.floor((c * W) / COLS), Math.floor((r * H) / ROWS), Math.floor(((c + 1) * W) / COLS), Math.floor(((r + 1) * H) / ROWS)));
    }
  }
  return { overall: pearson(a, b, 0, 0, W, H), worstTile };
}

export const MIN_OVERALL = Number(process.env.IMAGE_MIN_MATCH || 0.35);

export interface Audit {
  ok: boolean;
  problems: string[];
}

const AUDIT_PROMPT = `Image A is a 3D render of a café. Image B is an AI retouch of it that must contain exactly the same things.
Compare them and report every difference in CONTENT. Look closely at tables, counters, shelves, walls, the ceiling and the view through windows.

Report as a problem:
- anything in B that is not in A (people, cups, plates, food, plants, books, decor, lamps, signs, text, furniture, buildings...)
- anything in A that is missing from B
- an object that moved, changed shape, changed count, or became a different kind of object
- a clearly different material or colour on an object or wall
- a different camera position or framing

NOT problems: more realistic texture, softer shadows, better reflections, natural light falloff, film-like tone, less render noise.

Reply with only this JSON: {"added":[],"removed":[],"changed":[],"camera_changed":false}
Each list holds short descriptions of what you found, with where it is in the image. Empty lists mean no such differences.`;

async function auditJpeg(file: string): Promise<string> {
  const buf = await sharp(file).resize(1092, 728, { fit: "fill" }).jpeg({ quality: 85 }).toBuffer();
  return buf.toString("base64");
}

/** Throws if the audit could not run; the caller must then treat the image as unverified. */
export async function auditImages(renderFile: string, aiFile: string): Promise<Audit> {
  const [a, b] = await Promise.all([auditJpeg(renderFile), auditJpeg(aiFile)]);
  const client = new Anthropic({ maxRetries: 2, timeout: 120_000 });
  const res = await client.messages.create({
    model: AUDIT_MODEL,
    max_tokens: 2000,
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: "Image A (the 3D render):" },
          { type: "image", source: { type: "base64", media_type: "image/jpeg", data: a } },
          { type: "text", text: "Image B (the AI retouch):" },
          { type: "image", source: { type: "base64", media_type: "image/jpeg", data: b } },
          { type: "text", text: AUDIT_PROMPT },
        ],
      },
    ],
  });
  const text = res.content.filter((c): c is Anthropic.TextBlock => c.type === "text").map((c) => c.text).join("");
  const json = text.match(/\{[\s\S]*\}/)?.[0];
  if (!json) throw new Error("The audit returned no JSON");
  const r = JSON.parse(json) as { added?: unknown; removed?: unknown; changed?: unknown; camera_changed?: unknown };
  if (!Array.isArray(r.added) || !Array.isArray(r.removed) || !Array.isArray(r.changed)) throw new Error("The audit reply had the wrong shape");
  const problems = [
    ...r.added.map((s) => `added: ${String(s)}`),
    ...r.removed.map((s) => `removed: ${String(s)}`),
    ...r.changed.map((s) => `changed: ${String(s)}`),
    ...(r.camera_changed ? ["the camera changed"] : []),
  ];
  return { ok: problems.length === 0, problems };
}
