// Background job that prepares a design's images ahead of time, so the gallery opens with them ready:
//   Blender renders every area from several angles (render_views.py on the saved cafe.blend)
//   → the image model retouches each render → verify.ts checks nothing was invented → only then published.
// State lives in images/manifest.json. The job outlives the request that started it, and a new run resumes,
// skipping finished work. Self-hosted only: it needs a long-lived server, as the Blender routes already do.

import { spawn } from "node:child_process";
import { cpus } from "node:os";
import { mkdir, readFile, rename, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { MIN_OVERALL, auditImages, structureMatch } from "./verify";

const BLENDER_BIN = process.env.BLENDER_BIN || "blender";
const MODEL = process.env.OPENAI_IMAGE_MODEL || "gpt-image-1.5";
const QUALITY = process.env.OPENAI_IMAGE_QUALITY || "high";
const BASE_URL = (process.env.OPENAI_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, "");
const SAMPLES = Number(process.env.DESIGN_IMAGES_SAMPLES || 32);
const SIZE = "1536x1024"; // renders use this exact shape, so the model never has to invent content to fill a frame
const CONCURRENCY = 2;
const MAX_ATTEMPTS = 2;

const RETOUCH_PROMPT = `Retouch this architectural 3D render into a real interior photograph, as a professional photo retoucher would.
Only improve the realism of what is already visible: material texture, soft shadows, light falloff, reflections, camera-like tone.
ABSOLUTE RULES:
- Do NOT add anything: no people, cups, plates, food, plants, books, decor, lamps, signs, text, logos, furniture or any other object that is not already in the image. Empty surfaces stay empty.
- Do NOT remove, move, resize, reshape, duplicate or restyle any object, wall, window, door or fixture.
- Keep the exact camera, perspective, composition and room layout, and every object's position, colour and material type.
- Keep the view through windows as it is. Do not invent a new street, buildings or landscape.
- Keep existing text unchanged, or plain if it cannot be kept exact.
If something looks unfinished, leave it as it is. The result must overlay the input almost exactly.`;

export type AiStatus = "none" | "verified" | "rejected" | "unverified" | "failed";

export interface ImageItem {
  id: string;
  area: string;
  label: string;
  render?: string; // url, set once rendered
  ai?: string; // url, set ONLY after verification passed
  aiStatus: AiStatus;
  note?: string;
  match?: number;
}

export interface ImageManifest {
  id: string;
  state: "idle" | "running" | "done" | "error";
  phase?: string;
  error?: string;
  aiBlocked?: string; // the image API refuses every request (bad key, no credit): stop spending attempts
  model: string;
  items: ImageItem[];
  updatedAt: string;
}

export const validDesignId = (id: unknown): id is string => typeof id === "string" && /^[\w-]{1,64}$/.test(id);
const designDir = (id: string) => path.join(process.cwd(), "public", "blender-designs", id);
const imagesDir = (id: string) => path.join(designDir(id), "images");
const url = (id: string, f: string) => `/blender-designs/${id}/images/${f}`;

// on globalThis: Next compiles each route into its own module instance, and dev reloads would forget a running job
const g = globalThis as unknown as { __designImageJobs?: Map<string, Promise<void>>; __designImageQueue?: Promise<unknown> };
const jobs = (g.__designImageJobs ??= new Map());

export const isRunning = (id: string) => jobs.has(id);

export async function readManifest(id: string): Promise<ImageManifest | null> {
  try {
    const m = JSON.parse(await readFile(path.join(imagesDir(id), "manifest.json"), "utf8")) as ImageManifest;
    if (m.state === "running" && !isRunning(id)) {
      m.state = "idle"; // the server restarted mid-job
      m.phase = "Interrupted. Press Generate to continue.";
    }
    return m;
  } catch {
    return null;
  }
}

class Fatal extends Error {}

async function retouch(src: string, dest: string, correction?: string): Promise<void> {
  const form = new FormData();
  form.append("model", MODEL);
  form.append("prompt", correction ? `${RETOUCH_PROMPT}\nA previous attempt was rejected for these changes. Do not repeat them:\n${correction}` : RETOUCH_PROMPT);
  form.append("size", SIZE);
  form.append("quality", QUALITY);
  if (!/^gpt-image-2(-\d{4}|$)/.test(MODEL)) form.append("input_fidelity", "high"); // gpt-image-2 is always high and takes no such setting
  form.append("output_format", "jpeg");
  form.append("n", "1");
  form.append("image", new Blob([new Uint8Array(await readFile(src))], { type: "image/jpeg" }), "render.jpg");

  for (let attempt = 0; ; attempt++) {
    const r = await fetch(`${BASE_URL}/images/edits`, {
      method: "POST",
      headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` },
      body: form,
      signal: AbortSignal.timeout(300_000),
    });
    const d = (await r.json().catch(() => null)) as { data?: { b64_json?: string }[]; error?: { message?: string; code?: string } } | null;
    const b64 = d?.data?.[0]?.b64_json;
    if (r.ok && b64) {
      await writeFile(dest, Buffer.from(b64, "base64"));
      return;
    }
    const msg = d?.error?.message || `Image API ${r.status}`;
    const code = d?.error?.code ?? "";
    if (r.status === 401) throw new Fatal(`OpenAI rejected the API key (${code || "401"}).`);
    if (r.status === 403 || code === "insufficient_quota" || code === "billing_hard_limit_reached") throw new Fatal(`OpenAI refused: ${msg}`);
    if ((r.status === 429 || r.status >= 500) && attempt < 3) {
      await new Promise((res) => setTimeout(res, 15_000 * (attempt + 1)));
      continue;
    }
    throw new Error(msg);
  }
}

async function runJob(id: string, m: ImageManifest): Promise<void> {
  const dir = imagesDir(id);
  let writing: Promise<unknown> = Promise.resolve();
  const save = () => {
    m.updatedAt = new Date().toISOString();
    const snapshot = JSON.stringify(m, null, 2);
    writing = writing.then(async () => {
      const tmp = path.join(dir, ".manifest.tmp");
      await writeFile(tmp, snapshot);
      await rename(tmp, path.join(dir, "manifest.json"));
    });
    return writing;
  };

  // --- AI step: runs as each render lands, so results appear early
  let active = 0;
  const waiting: (() => void)[] = [];
  const slot = async () => {
    if (active >= CONCURRENCY) await new Promise<void>((r) => waiting.push(r));
    active++;
  };
  const release = () => {
    active--;
    waiting.shift()?.();
  };

  const aiStep = async (it: ImageItem) => {
    if (it.aiStatus === "verified" || it.aiStatus === "rejected" || !process.env.OPENAI_API_KEY) return;
    await slot();
    const src = path.join(dir, `${it.id}.jpg`);
    const tmp = path.join(dir, `.tmp_ai_${it.id}.jpg`);
    let correction: string | undefined;
    try {
      for (let attempt = 1; attempt <= MAX_ATTEMPTS && !m.aiBlocked; attempt++) {
        await retouch(src, tmp, correction);
        const s = await structureMatch(src, tmp);
        it.match = Number(s.overall.toFixed(3));
        let problems: string[];
        if (s.overall < MIN_OVERALL) {
          problems = ["the camera or layout changed"];
        } else {
          let audit;
          try {
            audit = await auditImages(src, tmp);
          } catch (e) {
            it.aiStatus = "unverified"; // no audit, no publishing. A later run retries.
            it.note = `Could not be checked: ${e instanceof Error ? e.message : "audit failed"}`;
            return;
          }
          problems = audit.problems;
        }
        if (!problems.length) {
          await rename(tmp, path.join(dir, `ai_${it.id}.jpg`));
          it.ai = url(id, `ai_${it.id}.jpg`);
          it.aiStatus = "verified";
          it.note = undefined;
          return;
        }
        correction = problems.join("\n");
        it.aiStatus = "rejected";
        it.note = problems.join("; ");
        await rename(tmp, path.join(dir, `rejected_${it.id}.jpg`)); // kept for inspection, never served by the gallery
      }
    } catch (e) {
      if (e instanceof Fatal) m.aiBlocked = e.message;
      else {
        it.aiStatus = "failed";
        it.note = e instanceof Error ? e.message : "Image generation failed";
      }
    } finally {
      await rm(tmp, { force: true }).catch(() => {});
      release();
      await save();
    }
  };

  const aiTasks: Promise<void>[] = [];
  const byId = new Map(m.items.map((i) => [i.id, i]));

  // --- render step
  m.phase = "Choosing camera angles in every area…";
  await save();
  const cwd = process.cwd();
  const dd = designDir(id);
  const threads = Math.max(2, cpus().length - 2); // leave cores free so the walkthrough stays smooth
  const blenderArgs = ["--background", path.join(dd, "cafe.blend"), "--threads", String(threads), "--python", path.join(cwd, "blender", "render_views.py"), "--", "--scene", path.join(dd, "scene.json"), "--out", dir, "--samples", String(SAMPLES), "--res", SIZE];
  const [cmd, args] = process.platform === "win32" ? [BLENDER_BIN, blenderArgs] : ["nice", ["-n", "10", BLENDER_BIN, ...blenderArgs]];
  await new Promise<void>((resolve, reject) => {
    const child = spawn(cmd, args as string[], { cwd });
    let buf = "", tail = "", chain = Promise.resolve();
    const onLine = (line: string) => {
      tail = (tail + line + "\n").slice(-1500);
      if (line.startsWith("PLAN_OK")) {
        chain = chain.then(async () => {
          const plan = JSON.parse(await readFile(path.join(dir, "plan.json"), "utf8")) as { id: string; area: string; label: string }[];
          m.items = plan.map((v) => byId.get(v.id) ?? { id: v.id, area: v.area, label: v.label, aiStatus: "none" });
          m.items.forEach((i) => byId.set(i.id, i));
          m.phase = `Rendering ${plan.length} views of every area…`;
          await save();
        });
      }
      const done = line.match(/^VIEW_DONE (\S+)/);
      if (done) {
        chain = chain.then(async () => {
          const it = byId.get(done[1]);
          if (!it) return;
          it.render = url(id, `${it.id}.jpg`);
          m.phase = `Rendered ${m.items.filter((i) => i.render).length} of ${m.items.length} views`;
          await save();
          aiTasks.push(aiStep(it));
        });
      }
    };
    child.stdout.on("data", (c: Buffer) => {
      buf += c.toString();
      const lines = buf.split("\n");
      buf = lines.pop() ?? "";
      lines.forEach(onLine);
    });
    child.stderr.on("data", (c: Buffer) => {
      tail = (tail + c.toString()).slice(-1500);
    });
    child.on("error", reject);
    child.on("close", (code) => {
      void chain.then(() => (code === 0 && tail.includes("VIEWS_OK") ? resolve() : reject(new Error(`Blender exited with ${code}: ${tail.slice(-400)}`))));
    });
  });

  m.phase = process.env.OPENAI_API_KEY ? "Finishing AI images…" : undefined;
  await save();
  await Promise.all(aiTasks);
  m.state = "done";
  m.phase = undefined;
  await save();
  await writing;
}

/** Start (or resume) a design's image job. Returns immediately. One Blender runs at a time; designs queue up. */
export async function startImageJob(id: string): Promise<void> {
  if (jobs.has(id)) return;
  const manifestFile = path.join(imagesDir(id), "manifest.json");
  const m: ImageManifest = { id, state: "running", phase: "Queued…", model: MODEL, items: [], updatedAt: new Date().toISOString() };
  const previous = g.__designImageQueue ?? Promise.resolve();
  // registered before the first await, so a double click cannot start two jobs
  const work = (async () => {
    await mkdir(imagesDir(id), { recursive: true });
    m.items = (await readManifest(id))?.items ?? [];
    await writeFile(manifestFile, JSON.stringify(m, null, 2));
    await previous.catch(() => {});
    await runJob(id, m);
  })()
    .catch(async (e) => {
      m.state = "error";
      m.phase = undefined;
      m.error = e instanceof Error ? e.message : "Image job failed";
      await writeFile(manifestFile, JSON.stringify(m, null, 2)).catch(() => {});
    })
    .finally(() => {
      jobs.delete(id);
    });
  jobs.set(id, work);
  g.__designImageQueue = work;
}
