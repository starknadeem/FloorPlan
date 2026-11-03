// Blender Cycles render route — reconstructs the current CafeScene in Blender (headless) and
// returns a path-traced photoreal PNG. This is the "beauty render" counterpart to the live
// three.js view: it renders the SAME geometry/GLB assets with true global illumination.
//
// It spawns:  blender --background --python blender/render_cafe.py -- --scene <json> --out <png> ...
// Requires a `blender` binary on PATH (Blender 3.6+). If missing, returns 501 like /api/render.

import { NextResponse } from "next/server";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

// Node runtime is the default for route handlers (needed for child_process + fs).
// Note: this Next config has `cacheComponents` on, which forbids `export const runtime`.
export const maxDuration = 300;

interface Body {
  scene?: unknown;
  cam?: number[]; // [px,py,pz, tx,ty,tz] in three.js world coords
  samples?: number;
  res?: [number, number];
  ceiling?: boolean;
}

const BLENDER_BIN = process.env.BLENDER_BIN || "blender";

function runBlender(args: string[], cwd: string): Promise<{ code: number; out: string }> {
  return new Promise((resolve, reject) => {
    const child = spawn(BLENDER_BIN, args, { cwd });
    let out = "";
    child.stdout.on("data", (d) => (out += d.toString()));
    child.stderr.on("data", (d) => (out += d.toString()));
    child.on("error", reject); // ENOENT when blender isn't installed
    child.on("close", (code) => resolve({ code: code ?? -1, out }));
  });
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as Body;
  if (!body?.scene || typeof body.scene !== "object") {
    return NextResponse.json({ error: "No scene provided." }, { status: 400 });
  }

  const cwd = process.cwd(); // webapp/
  const script = path.join(cwd, "blender", "render_cafe.py");
  const samples = Math.min(Math.max(body.samples ?? 96, 8), 1024);
  const [rw, rh] = body.res ?? [1600, 900];

  const dir = await mkdtemp(path.join(tmpdir(), "cafe-blender-"));
  const sceneFile = path.join(dir, "scene.json");
  const outFile = path.join(dir, "render.png");

  try {
    await writeFile(sceneFile, JSON.stringify(body.scene));

    const args = [
      "--background",
      "--python", script,
      "--",
      "--scene", sceneFile,
      "--out", outFile,
      "--samples", String(samples),
      "--res", `${rw}x${rh}`,
    ];
    if (body.ceiling === false) args.push("--no-ceiling");
    if (Array.isArray(body.cam) && body.cam.length === 6) {
      args.push("--cam", body.cam.join(","));
    }

    const { code, out } = await runBlender(args, cwd);
    if (code !== 0 || !out.includes("RENDER_OK")) {
      const tail = out.split("\n").slice(-25).join("\n");
      return NextResponse.json(
        { error: "Blender render failed.", detail: tail.slice(0, 1500) },
        { status: 500 },
      );
    }

    const png = await readFile(outFile);
    const dataUrl = `data:image/png;base64,${png.toString("base64")}`;
    return NextResponse.json({ imageUrl: dataUrl });
  } catch (err) {
    const e = err as NodeJS.ErrnoException;
    if (e?.code === "ENOENT") {
      return NextResponse.json(
        {
          error:
            "Blender is not installed or not on PATH. Install Blender (3.6+) and ensure the " +
            "`blender` command works, or set BLENDER_BIN in webapp/.env.local to its full path. " +
            "The live 3D view and PNG export work without it.",
          notConfigured: true,
        },
        { status: 501 },
      );
    }
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => {});
  }
}
