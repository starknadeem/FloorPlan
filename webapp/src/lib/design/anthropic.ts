import Anthropic from "@anthropic-ai/sdk";
import type { LayoutItemCtx, LayoutResult } from "./layout";

const MODEL = process.env.ANTHROPIC_MODEL || "claude-opus-5-5";
const STYLES = ["industrial-chic", "scandinavian", "cozy-warm"];

export interface DesignChoice {
  style: string;
  rationale: string;
}

/** Ask the model to choose the best interior style for a described coffee shop. Cheap text call. */
export async function chooseStyle(summary: string): Promise<DesignChoice> {
  const client = new Anthropic();
  const res = await client.messages.create({
    model: MODEL,
    max_tokens: 600,
    output_config: { effort: "low" },
    system:
      `You are an interior designer for coffee shops. Choose the single best interior style for the ` +
      `described space from EXACTLY these keys: ${STYLES.join(", ")}. ` +
      `Return ONLY a JSON object: {"style":"<one key>","rationale":"<one short sentence>"}.`,
    messages: [{ role: "user", content: summary || "A small coffee shop." }],
  });

  const text = res.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("\n");
  const m = text.match(/\{[\s\S]*\}/);
  let obj: { style?: string; rationale?: string } = {};
  try {
    obj = m ? JSON.parse(m[0]) : {};
  } catch {
    obj = {};
  }
  return {
    style: obj.style && STYLES.includes(obj.style) ? obj.style : "industrial-chic",
    rationale: obj.rationale || "",
  };
}

/**
 * Ask the model, acting as a café space planner, to pick each fixture's facing + model
 * variant. It is seeded with a deterministic facing suggestion (per fixture) so it only
 * needs to correct obvious mistakes and add tasteful variety. Returns rotation + model
 * overrides keyed by fixture id; anything it omits keeps the deterministic default.
 */
export async function planLayout(items: LayoutItemCtx[]): Promise<LayoutResult> {
  const client = new Anthropic();
  const res = await client.messages.create({
    model: MODEL,
    max_tokens: 8000,
    output_config: { effort: "low" },
    system:
      `You are a café space planner placing furniture in a 3D scene.\n` +
      `COORDINATES: plan space, x→right, y→up-the-page, metres. A fixture's "rotation" is in ` +
      `degrees, counter-clockwise positive, where 0 means its FRONT faces plan +Y.\n` +
      `RULES:\n` +
      `- Seating (chair, stool) faces the table it serves; a sofa/banquette faces into the room (its back to the wall).\n` +
      `- Appliances & service pieces (counter, cashier, fridge, freezer, espresso_machine, grinder, oven, sink, ` +
      `dishwasher, display_case, cooling_case, shelving, monitor, menu_board, toilet) put their back to the nearest ` +
      `wall and their front/working face toward the room.\n` +
      `- "suggestedRotation" is a solid geometric default — KEEP it unless it is clearly wrong; then correct it.\n` +
      `- For "model", pick ONE key from that item's "variants" list to suit the piece (e.g. round tables read as ` +
      `café bistro tables; use the long sofa for a wide banquette footprint; bar stools at tall counters). If the ` +
      `list is empty or no variant is clearly better, omit "model".\n` +
      `OUTPUT: ONLY a JSON array, one object per fixture you want to set: ` +
      `[{"id":"fx_0","rotation":90,"model":"table_round"}, ...]. Omit "model" when not choosing one. No prose.`,
    messages: [{ role: "user", content: JSON.stringify(items) }],
  });

  const text = res.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("\n");
  const m = text.match(/\[[\s\S]*\]/);
  const rotations: Record<string, number> = {};
  const models: Record<string, string> = {};
  if (m) {
    try {
      const arr = JSON.parse(m[0]) as Array<{ id?: string; rotation?: number; model?: string }>;
      for (const it of arr) {
        if (!it || typeof it.id !== "string") continue;
        if (typeof it.rotation === "number" && Number.isFinite(it.rotation)) rotations[it.id] = it.rotation;
        if (typeof it.model === "string" && it.model) models[it.id] = it.model;
      }
    } catch {
      // fall through — caller merges with the deterministic baseline
    }
  }
  return { rotations, models };
}
