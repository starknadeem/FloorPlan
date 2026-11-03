import { NextResponse } from "next/server";
import { enhanceToPhotoreal, NotConfiguredError } from "@/lib/render/photoreal";

export const maxDuration = 300;

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const image = typeof body?.image === "string" ? body.image : "";
    const prompt = typeof body?.prompt === "string" ? body.prompt : "";
    if (!image) return NextResponse.json({ error: "No image provided." }, { status: 400 });

    const result = await enhanceToPhotoreal(image, prompt);
    return NextResponse.json(result);
  } catch (err) {
    if (err instanceof NotConfiguredError) {
      return NextResponse.json({ error: err.message, notConfigured: true }, { status: 501 });
    }
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
