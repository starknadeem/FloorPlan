import { NextResponse } from "next/server";
import sharp from "sharp";
import { parsePlanImage } from "@/lib/parser/anthropic";
import { parsedPlanToScene } from "@/lib/parser/normalize";
import { elevateCounterTopItems } from "@/lib/design/furnish";

export const maxDuration = 300;

const MAX_UPLOAD = 25 * 1024 * 1024; // 25 MB
const TILE = 1568;

/** Split a large sheet into a 2×2 grid of overlapping full-resolution crops (each ≤ 1568 px), labelled with the
 *  region they cover as fractions of the page so the model maps them back onto the overview. */
async function zoomTiles(input: Buffer): Promise<{ data: string; label: string }[]> {
  const { data: page, info } = await sharp(input).rotate().toBuffer({ resolveWithObject: true });
  const W = info.width, H = info.height;
  if (Math.max(W, H) < TILE * 1.3) return [];
  const out: { data: string; label: string }[] = [];
  const ov = 0.12; // overlap so nothing is cut in half at a seam
  for (const [fy0, fy1] of [[0, 0.5 + ov / 2], [0.5 - ov / 2, 1]]) {
    for (const [fx0, fx1] of [[0, 0.5 + ov / 2], [0.5 - ov / 2, 1]]) {
      const left = Math.round(fx0 * W), top = Math.round(fy0 * H);
      const width = Math.min(Math.round((fx1 - fx0) * W), W - left), height = Math.min(Math.round((fy1 - fy0) * H), H - top);
      const buf = await sharp(page).extract({ left, top, width, height })
        .resize({ width: TILE, height: TILE, fit: "inside", withoutEnlargement: true }).jpeg({ quality: 90 }).toBuffer();
      out.push({
        data: buf.toString("base64"),
        label: `ZOOM of the same page: x ${Math.round(fx0 * 100)}–${Math.round(fx1 * 100)}% from the left, y ${Math.round(fy0 * 100)}–${Math.round(fy1 * 100)}% from the top.`,
      });
    }
  }
  return out;
}

export async function POST(req: Request) {
  try {
    if (!process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json(
        { error: "ANTHROPIC_API_KEY is not set on the server (webapp/.env.local)." },
        { status: 500 },
      );
    }

    const form = await req.formData();
    const file = form.get("file");
    if (!file || !(file instanceof File)) {
      return NextResponse.json({ error: "No file uploaded (field 'file')." }, { status: 400 });
    }
    if (file.size > MAX_UPLOAD) {
      return NextResponse.json({ error: "File too large (max 25 MB)." }, { status: 400 });
    }

    const inputBuffer = Buffer.from(await file.arrayBuffer());

    // Normalize + downscale so dimensions/text stay legible while keeping cost/limits sane.
    const jpeg = await sharp(inputBuffer)
      .rotate() // honor EXIF orientation
      .resize({ width: 1568, height: 1568, fit: "inside", withoutEnlargement: true })
      .jpeg({ quality: 90 })
      .toBuffer();

    const base64 = jpeg.toString("base64");

    // Zoom tiles at full resolution. A whole A1/A2 sheet squeezed to 1568 px leaves a chair ~20 px wide, so seating
    // and small equipment numbers were miscounted (16 terrace tables instead of 7, stands read as benches).
    const tiles = await zoomTiles(inputBuffer);

    const started = Date.now();
    const { plan, usage, model } = await parsePlanImage(base64, "image/jpeg", tiles);
    // lift counter-top machines onto counters + clamp oversized appliance footprints
    const scene = elevateCounterTopItems(parsedPlanToScene(plan, file.name || "upload"));

    // rough cost estimate for claude-opus-5-5 ($4 / $20 per MTok)
    const estCostUsd =
      (usage.input_tokens / 1_000_000) * 4 + (usage.output_tokens / 1_000_000) * 20;

    return NextResponse.json({
      scene,
      meta: {
        model,
        usage,
        estCostUsd: Number(estCostUsd.toFixed(4)),
        elapsedMs: Date.now() - started,
        counts: {
          walls: scene.walls.length,
          openings: scene.openings.length,
          rooms: scene.rooms.length,
          fixtures: scene.fixtures.length,
          legend: scene.legend.length,
          issues: scene.issues?.length ?? 0,
        },
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("[/api/parse] error:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
