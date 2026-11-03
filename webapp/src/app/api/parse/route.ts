import { NextResponse } from "next/server";
import sharp from "sharp";
import { parsePlanImage } from "@/lib/parser/anthropic";
import { parsedPlanToScene } from "@/lib/parser/normalize";

export const maxDuration = 300;

const MAX_UPLOAD = 25 * 1024 * 1024; // 25 MB

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

    const started = Date.now();
    const { plan, usage, model } = await parsePlanImage(base64, "image/jpeg");
    const scene = parsedPlanToScene(plan, file.name || "upload");

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
