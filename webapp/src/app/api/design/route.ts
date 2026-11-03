import { NextResponse } from "next/server";
import { chooseStyle } from "@/lib/design/anthropic";

export const maxDuration = 120;

export async function POST(req: Request) {
  try {
    if (!process.env.ANTHROPIC_API_KEY) {
      return NextResponse.json({ error: "ANTHROPIC_API_KEY is not set." }, { status: 500 });
    }
    const body = await req.json().catch(() => ({}));
    const summary = typeof body?.summary === "string" ? body.summary : "";
    const choice = await chooseStyle(summary);
    return NextResponse.json(choice);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
