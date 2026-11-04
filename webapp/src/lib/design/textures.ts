// Phase 4.1 — procedural PBR textures (generated on a canvas, no external files).
// Phase 4.3 — real photo-based CC0 PBR materials loaded from /public/textures (ambientCG).
// Cached by (type,color). Client-only (used inside R3F components).

import * as THREE from "three";

const cache = new Map<string, THREE.CanvasTexture>();

// ---------- real image-based PBR materials (ambientCG, CC0) ----------
export type PbrName = "terrazzo" | "concrete" | "marble" | "wood" | "fabric" | "oak" | "plaster";
export interface PbrMaps {
  map: THREE.Texture;
  normalMap: THREE.Texture;
  roughnessMap: THREE.Texture;
}

// Share decoded images across textures so each tiling variant doesn't re-fetch.
if (typeof window !== "undefined") THREE.Cache.enabled = true;
const _loader = typeof window !== "undefined" ? new THREE.TextureLoader() : null;
const _texCache = new Map<string, THREE.Texture>();

function _load(url: string, srgb: boolean, rx: number, ry: number): THREE.Texture {
  const key = `${url}:${rx}:${ry}`;
  const hit = _texCache.get(key);
  if (hit) return hit;
  const t = _loader ? _loader.load(url) : new THREE.Texture();
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.anisotropy = 8;
  t.repeat.set(rx, ry);
  _texCache.set(key, t);
  return t;
}

/** PBR material maps for a named CC0 material, tiled `rx`×`ry`. */
export function pbr(name: PbrName, rx = 1, ry = 1): PbrMaps {
  return {
    map: _load(`/textures/${name}/color.jpg`, true, rx, ry),
    normalMap: _load(`/textures/${name}/normal.jpg`, false, rx, ry),
    roughnessMap: _load(`/textures/${name}/rough.jpg`, false, rx, ry),
  };
}

/** The Coffee Berry wordmark as a transparent texture, optionally tiled `n`× horizontally. */
export function brandLogo(n = 1): THREE.Texture {
  return _load("/brand/coffee-berry-logo.png", true, n, 1);
}

function ctx(size: number): readonly [HTMLCanvasElement, CanvasRenderingContext2D] {
  const cv = document.createElement("canvas");
  cv.width = cv.height = size;
  return [cv, cv.getContext("2d")!] as const;
}

function toTex(cv: HTMLCanvasElement, rx: number, ry: number): THREE.CanvasTexture {
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(rx, ry);
  t.anisotropy = 4;
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function vary(base: THREE.Color, amt: number): string {
  const c = base.clone();
  const f = 1 + (Math.random() * 2 - 1) * amt;
  c.multiplyScalar(f);
  return `#${c.getHexString()}`;
}

/** Wood with plank seams + grain streaks, tinted to `color`. */
export function woodTexture(color: string): THREE.CanvasTexture {
  const key = `wood:${color}`;
  const hit = cache.get(key);
  if (hit) return hit;
  if (typeof document === "undefined") return new THREE.CanvasTexture(null as unknown as HTMLCanvasElement);
  const S = 256;
  const [cv, g] = ctx(S);
  const base = new THREE.Color(color);
  g.fillStyle = `#${base.getHexString()}`;
  g.fillRect(0, 0, S, S);
  const planks = 4;
  for (let i = 0; i < planks; i++) {
    const x = (i * S) / planks;
    g.fillStyle = vary(base, 0.06);
    g.fillRect(x, 0, S / planks, S);
    g.strokeStyle = "rgba(0,0,0,0.18)";
    g.lineWidth = 2;
    g.beginPath(); g.moveTo(x, 0); g.lineTo(x, S); g.stroke();
  }
  for (let i = 0; i < 120; i++) {
    g.strokeStyle = `rgba(${Math.random() > 0.5 ? "255,255,255" : "0,0,0"},0.04)`;
    g.lineWidth = 1;
    const y = Math.random() * S;
    g.beginPath(); g.moveTo(0, y); g.bezierCurveTo(S / 3, y + (Math.random() * 6 - 3), (2 * S) / 3, y + (Math.random() * 6 - 3), S, y); g.stroke();
  }
  const t = toTex(cv, 1, 1);
  cache.set(key, t);
  return t;
}

/** Flagstone-ish floor: irregular cells with grout, tinted to `color`. */
export function stoneTexture(color: string): THREE.CanvasTexture {
  const key = `stone:${color}`;
  const hit = cache.get(key);
  if (hit) return hit;
  if (typeof document === "undefined") return new THREE.CanvasTexture(null as unknown as HTMLCanvasElement);
  const S = 256;
  const [cv, g] = ctx(S);
  const base = new THREE.Color(color);
  g.fillStyle = `#${base.clone().multiplyScalar(0.7).getHexString()}`; // grout
  g.fillRect(0, 0, S, S);
  const cells = 5;
  const cw = S / cells;
  for (let ix = 0; ix < cells; ix++) {
    for (let iy = 0; iy < cells; iy++) {
      const pad = 3 + Math.random() * 3;
      const jx = (Math.random() * 4 - 2);
      const jy = (Math.random() * 4 - 2);
      g.fillStyle = vary(base, 0.1);
      g.beginPath();
      g.rect(ix * cw + pad + jx, iy * cw + pad + jy, cw - pad * 2, cw - pad * 2);
      g.fill();
    }
  }
  // speckle
  for (let i = 0; i < 400; i++) {
    g.fillStyle = `rgba(${Math.random() > 0.5 ? "255,255,255" : "0,0,0"},0.05)`;
    g.fillRect(Math.random() * S, Math.random() * S, 1.5, 1.5);
  }
  const t = toTex(cv, 0.6, 0.6);
  cache.set(key, t);
  return t;
}
