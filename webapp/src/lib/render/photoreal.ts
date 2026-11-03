// Phase 5 — AI photoreal enhancement (generative render layer).
//
// Claude does NOT generate images. Turning a 3D snapshot into a photoreal / architectural-viz render
// needs an image-to-image model conditioned on the captured view. This is the single integration point.
//
// WIRED: fal.ai FLUX.1 [dev] image-to-image (https://fal.ai/models/fal-ai/flux/dev/image-to-image).
// Add FAL_KEY to webapp/.env.local to enable it. (Replicate / Stability branches are left as stubs.)
//
// NOTE: this request has not been run end-to-end yet (no FAL_KEY available in this environment). The
// contract below follows fal.ai's documented sync API; if a field name differs for your account, adjust
// here — it is the only place that talks to the provider.

export class NotConfiguredError extends Error {}

const FAL_IMG2IMG = "https://fal.run/fal-ai/flux/dev/image-to-image";

export async function enhanceToPhotoreal(
  imageDataUrl: string,
  prompt: string,
): Promise<{ imageUrl: string }> {
  const falKey = process.env.FAL_KEY;
  const otherKey = process.env.REPLICATE_API_TOKEN || process.env.STABILITY_API_KEY;

  if (!falKey && !otherKey) {
    throw new NotConfiguredError(
      "AI photoreal rendering needs an image-generation API key. Add FAL_KEY (recommended) — or " +
        "REPLICATE_API_TOKEN / STABILITY_API_KEY — to webapp/.env.local. The 3D snapshot and isometric " +
        "export work without it.",
    );
  }

  if (falKey) {
    // img2img keeps the camera/layout of the 3D snapshot and re-renders it photoreal.
    // strength ~0.55–0.7: higher = more realism but more drift from the captured geometry.
    const res = await fetch(FAL_IMG2IMG, {
      method: "POST",
      headers: { Authorization: `Key ${falKey}`, "content-type": "application/json" },
      body: JSON.stringify({
        image_url: imageDataUrl, // fal accepts a data: URI
        prompt,
        strength: 0.62,
        num_inference_steps: 40,
        guidance_scale: 3.5,
        image_size: "landscape_16_9",
        enable_safety_checker: true,
      }),
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      throw new Error(`fal.ai request failed (${res.status}). ${detail.slice(0, 300)}`);
    }
    const data = (await res.json().catch(() => ({}))) as { images?: Array<{ url?: string }> };
    const url = data?.images?.[0]?.url;
    if (!url) throw new Error("fal.ai returned no image. Check the model id / response shape in photoreal.ts.");
    return { imageUrl: url };
  }

  // Replicate / Stability: add the analogous img2img call here if you use those instead of fal.ai.
  throw new NotConfiguredError(
    "Found REPLICATE_API_TOKEN/STABILITY_API_KEY but only the fal.ai path is wired. Either set FAL_KEY, " +
      "or implement the Replicate/Stability img2img call in src/lib/render/photoreal.ts.",
  );
}
