// Phase 5 — AI photoreal enhancement (generative render layer).
//
// NOTE: Anthropic/Claude does NOT generate images. Turning a 3D snapshot into a Reference-A photoreal
// render requires an image-generation model (e.g. fal.ai FLUX img2img / ControlNet, Stability, or
// Replicate) conditioned on the captured view (and ideally a depth/edge map of the scene).
//
// This is the single integration point. It is intentionally not wired to a specific provider (an
// untested external call would be unreliable). When you add a provider key to webapp/.env.local, wire
// the request here and return the resulting image URL/data.

export class NotConfiguredError extends Error {}

export async function enhanceToPhotoreal(
  _imageB64: string,
  _prompt: string,
): Promise<{ imageUrl: string }> {
  const key =
    process.env.FAL_KEY || process.env.REPLICATE_API_TOKEN || process.env.STABILITY_API_KEY;

  if (!key) {
    throw new NotConfiguredError(
      "AI photoreal rendering needs an image-generation API key. Add FAL_KEY (or REPLICATE_API_TOKEN / " +
        "STABILITY_API_KEY) to webapp/.env.local, then wire the provider call in src/lib/render/photoreal.ts. " +
        "The 3D snapshot and isometric export work without it.",
    );
  }

  // Integration point — send `_imageB64` + `_prompt` (+ optional depth/edge map) to your image model
  // here and return { imageUrl }. Left unwired on purpose.
  throw new NotConfiguredError(
    "An image-generation key was found, but the provider request is not wired yet. Implement it in " +
      "src/lib/render/photoreal.ts (send the snapshot + prompt to your model, return the image URL).",
  );
}
