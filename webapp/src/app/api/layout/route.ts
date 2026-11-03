import { NextResponse } from "next/server";
import type { CafeScene } from "@/types/cafescene";
import { planLayout } from "@/lib/design/anthropic";
import { applyLayout, buildLayoutContext, deterministicResult, type LayoutResult } from "@/lib/design/layout";

export const maxDuration = 120;

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(() => ({}));
    const scene = body?.scene as CafeScene | undefined;
    if (!scene || !Array.isArray(scene.fixtures)) {
      return NextResponse.json({ error: "Request body must include a valid scene." }, { status: 400 });
    }

    // Deterministic baseline — always available, no API key needed.
    const base = deterministicResult(scene);
    let result: LayoutResult = base;
    let usedAI = false;
    let note = "Arranged furniture facing (geometry).";

    if (process.env.ANTHROPIC_API_KEY) {
      try {
        const ai = await planLayout(buildLayoutContext(scene));
        // AI overlays the baseline: keep geometric facing where AI said nothing.
        result = {
          rotations: { ...base.rotations, ...ai.rotations },
          models: { ...base.models, ...ai.models },
        };
        usedAI = true;
        note = "AI arranged furniture facing and picked models.";
      } catch (e) {
        note = "AI step failed — used geometry facing. " + (e instanceof Error ? e.message : "");
      }
    } else {
      note = "No AI key — used geometry facing and placed WC fixtures.";
    }

    const next = applyLayout(scene, result);
    return NextResponse.json({ scene: next, usedAI, note, added: next.fixtures.length - scene.fixtures.length });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
