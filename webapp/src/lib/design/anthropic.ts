import Anthropic from "@anthropic-ai/sdk";

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
