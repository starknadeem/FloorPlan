import Anthropic from "@anthropic-ai/sdk";
import { SYSTEM_PROMPT, buildUserText } from "./prompt";
import type { ParsedPlan } from "./types";

const MODEL = process.env.ANTHROPIC_MODEL || "claude-opus-5-5";
const EFFORT = (process.env.ANTHROPIC_EFFORT || "medium") as
  | "low"
  | "medium"
  | "high"
  | "xhigh"
  | "max";
const MAX_TOKENS = Number(process.env.ANTHROPIC_MAX_TOKENS || 40000);

export interface ParseResult {
  plan: ParsedPlan;
  usage: { input_tokens: number; output_tokens: number };
  model: string;
}

/** Extract a JSON object from a possibly-fenced / prose-wrapped text block. */
function extractJson(text: string): unknown {
  let t = text.trim();
  // strip ```json ... ``` or ``` ... ``` fences if present
  const fence = t.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence) t = fence[1].trim();
  // slice from first { to last }
  const start = t.indexOf("{");
  const end = t.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("No JSON object found in model response");
  }
  return JSON.parse(t.slice(start, end + 1));
}

export async function parsePlanImage(
  imageBase64: string,
  mediaType: "image/jpeg" | "image/png" | "image/webp",
  tiles: { data: string; label: string }[] = [],
): Promise<ParseResult> {
  const client = new Anthropic(); // reads ANTHROPIC_API_KEY from env

  // Streaming avoids HTTP timeouts on large outputs (recommended for big max_tokens).
  const stream = client.messages.stream({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: SYSTEM_PROMPT,
    output_config: { effort: EFFORT },
    messages: [
      {
        role: "user",
        content: [
          { type: "text", text: "WHOLE PAGE (overview: use it for the outline, dimensions and coordinates):" },
          { type: "image", source: { type: "base64", media_type: mediaType, data: imageBase64 } },
          ...tiles.flatMap((t) => [
            { type: "text" as const, text: t.label + " Read seating symbols, circled numbers and small labels here; express positions in the same metre frame as the overview." },
            { type: "image" as const, source: { type: "base64" as const, media_type: "image/jpeg" as const, data: t.data } },
          ]),
          { type: "text", text: buildUserText() },
        ],
      },
    ],
  });
  const response = await stream.finalMessage();

  if (response.stop_reason === "refusal") {
    throw new Error("The model declined to process this image.");
  }
  if (response.stop_reason === "max_tokens") {
    throw new Error(
      "Model output was cut off (max_tokens reached). The plan is large — increase ANTHROPIC_MAX_TOKENS or lower effort.",
    );
  }

  const text = response.content
    .filter((b): b is Anthropic.TextBlock => b.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();

  if (!text) throw new Error("Empty response from model");

  const plan = extractJson(text) as ParsedPlan;

  return {
    plan,
    usage: {
      input_tokens: response.usage.input_tokens,
      output_tokens: response.usage.output_tokens,
    },
    model: response.model,
  };
}
