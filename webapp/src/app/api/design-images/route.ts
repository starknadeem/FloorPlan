// Images of a Blender design. GET reads what is ready (the gallery polls this). POST starts or resumes the
// background job in lib/design-images/job.ts; that job, not the request, does the work.

import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { isRunning, readManifest, startImageJob, validDesignId } from "@/lib/design-images/job";

export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("id");
  if (!validDesignId(id)) return Response.json({ error: "Bad id" }, { status: 400 });
  const manifest = await readManifest(id);
  let stills: { url: string; label: string }[] = [];
  try {
    const meta = JSON.parse(await readFile(path.join(process.cwd(), "public", "blender-designs", id, "meta.json"), "utf8")) as { stills?: typeof stills };
    stills = meta.stills ?? [];
  } catch {
    return Response.json({ error: "Design not found" }, { status: 404 });
  }
  return Response.json({ manifest, stills, running: isRunning(id), aiEnabled: Boolean(process.env.OPENAI_API_KEY) });
}

export async function POST(req: Request) {
  const { id } = (await req.json().catch(() => ({}))) as { id?: unknown };
  if (!validDesignId(id)) return Response.json({ error: "Bad id" }, { status: 400 });
  try {
    await access(path.join(process.cwd(), "public", "blender-designs", id, "cafe.blend"));
  } catch {
    return Response.json({ error: "This design has no saved Blender model." }, { status: 404 });
  }
  await startImageJob(id);
  return Response.json({ started: true }, { status: 202 });
}
