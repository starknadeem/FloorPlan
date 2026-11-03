// Tour route — turns a CafeScene into a walkable photoreal 360 tour, streaming live progress.
//
// Spawns Blender headless to render an equirectangular panorama per room, parses Blender's
// PANO_TOTAL / PANO_DONE markers from stdout, and streams NDJSON progress events to the client:
//   {type:"progress", percent, label, done, total}
//   {type:"done", tourId, baseUrl, stops}
//   {type:"error", error, detail?, notConfigured?}
// Panos are written under public/tours/<id>/ so they're served statically.
//
// Requires a `blender` binary on PATH (or BLENDER_BIN in .env.local).

import { spawn } from "node:child_process";
import { mkdtemp, writeFile, readFile, rm, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import crypto from "node:crypto";

export const maxDuration = 300;

interface Body {
  scene?: unknown;
  samples?: number;
  panoRes?: [number, number];
  maxStops?: number;
}

const BLENDER_BIN = process.env.BLENDER_BIN || "blender";

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Body;
  if (!body?.scene || typeof body.scene !== "object") {
    return new Response(JSON.stringify({ error: "No scene provided." }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const cwd = process.cwd(); // webapp/
  const script = path.join(cwd, "blender", "render_cafe.py");
  // Fast defaults: modest resolution + samples (denoiser cleans it) keep each room short on CPU.
  const samples = Math.min(Math.max(body.samples ?? 16, 8), 512);
  const [pw, ph] = body.panoRes ?? [1536, 768];
  const maxStops = Math.min(Math.max(body.maxStops ?? 10, 1), 40);

  const id = crypto.randomUUID().slice(0, 8);
  const tourDir = path.join(cwd, "public", "tours", id);
  const tmp = await mkdtemp(path.join(tmpdir(), "cafe-tour-"));
  const sceneFile = path.join(tmp, "scene.json");

  const stream = new ReadableStream({
    async start(controller) {
      const enc = new TextEncoder();
      const send = (obj: unknown) => controller.enqueue(enc.encode(JSON.stringify(obj) + "\n"));

      try {
        await mkdir(tourDir, { recursive: true });
        await writeFile(sceneFile, JSON.stringify(body.scene));
        send({ type: "progress", percent: 4, label: "Assembling the café in Blender…" });

        const args = [
          "--background", "--python", script, "--",
          "--scene", sceneFile,
          "--pano-out", tourDir,
          "--pano-res", `${pw}x${ph}`,
          "--samples", String(samples),
          "--max-stops", String(maxStops),
        ];

        const child = spawn(BLENDER_BIN, args, { cwd });
        let total = 0;
        let done = 0;
        let out = "";
        let buf = "";
        let spawnErr: NodeJS.ErrnoException | null = null;

        const onLine = (line: string) => {
          if (line.startsWith("PANO_TOTAL ")) {
            total = parseInt(line.slice(11).trim(), 10) || 0;
            send({ type: "progress", percent: 8, label: `Rendering ${total} room view${total === 1 ? "" : "s"}…`, total, done: 0 });
          } else if (line.startsWith("PANO_DONE ")) {
            done += 1;
            const name = line.slice(10).split(" ").slice(1).join(" ").trim();
            const percent = total ? Math.min(98, 8 + Math.round((done / total) * 90)) : 50;
            send({ type: "progress", percent, label: `Rendered ${done}/${total}${name ? ` · ${name}` : ""}`, total, done });
          }
        };

        child.stdout.on("data", (d: Buffer) => {
          const s = d.toString();
          out += s;
          buf += s;
          let i;
          while ((i = buf.indexOf("\n")) >= 0) {
            onLine(buf.slice(0, i));
            buf = buf.slice(i + 1);
          }
        });
        child.stderr.on("data", (d: Buffer) => (out += d.toString()));

        const code: number = await new Promise((res) => {
          child.on("error", (e) => { spawnErr = e as NodeJS.ErrnoException; res(-1); });
          child.on("close", (c) => res(c ?? -1));
        });

        if (spawnErr && (spawnErr as NodeJS.ErrnoException).code === "ENOENT") {
          send({
            type: "error",
            notConfigured: true,
            error: "Blender is not installed or not on PATH. Install Blender (3.6+) or set BLENDER_BIN in webapp/.env.local.",
          });
          await rm(tourDir, { recursive: true, force: true }).catch(() => {});
          return;
        }
        if (code !== 0 || !out.includes("PANO_OK")) {
          await rm(tourDir, { recursive: true, force: true }).catch(() => {});
          send({ type: "error", error: "Blender tour render failed.", detail: out.split("\n").slice(-25).join("\n").slice(0, 1500) });
          return;
        }

        const manifest = JSON.parse(await readFile(path.join(tourDir, "manifest.json"), "utf8")) as {
          stops: unknown[];
        };
        send({ type: "done", tourId: id, baseUrl: `/tours/${id}`, stops: manifest.stops, percent: 100 });
      } catch (err) {
        await rm(tourDir, { recursive: true, force: true }).catch(() => {});
        send({ type: "error", error: err instanceof Error ? err.message : "Unknown error" });
      } finally {
        await rm(tmp, { recursive: true, force: true }).catch(() => {});
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "application/x-ndjson; charset=utf-8",
      "cache-control": "no-store, no-transform",
    },
  });
}
