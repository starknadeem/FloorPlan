"use client";

// Photographic look for the web walkthrough: HDRI sky behind the glazing, interior reflections,
// screen-space ambient occlusion (contact shadows under chairs, in corners), bloom on the LED
// strips / bulbs / logo, AgX tone mapping (same transform Blender's Cycles renders use), SMAA,
// a light vignette, and real planar reflections in mirrors.

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { EffectComposer, N8AO, Bloom, SMAA, ToneMapping, Vignette, HueSaturation, BrightnessContrast } from "@react-three/postprocessing";
import { ToneMappingMode } from "postprocessing";
import * as THREE from "three";
import { HDRLoader } from "three/examples/jsm/loaders/HDRLoader.js";
import { Reflector } from "three/examples/jsm/objects/Reflector.js";

/**
 * Pick the effects tier once at load: integrated / mobile / software GPUs get the cheap AO preset, 1x DPR and
 * a smaller shadow map. `?q=high|low` overrides. (Switching live rebuilds the composer mid-frame.)
 */
export function detectQuality(): "high" | "low" {
  if (typeof window === "undefined") return "high";
  const q = new URLSearchParams(window.location.search).get("q");
  if (q === "high" || q === "low") return q;
  if (/Android|iPhone|iPad|Mobile/i.test(navigator.userAgent)) return "low";
  try {
    const gl = document.createElement("canvas").getContext("webgl2");
    const ext = gl?.getExtension("WEBGL_debug_renderer_info");
    const r = gl && ext ? String(gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)) : "";
    gl?.getExtension("WEBGL_lose_context")?.loseContext();
    if (/Intel|SwiftShader|llvmpipe|Mali|Adreno|PowerVR|Microsoft Basic/i.test(r)) return "low";
  } catch {
    /* unknown GPU: assume capable */
  }
  return "high";
}

export const SKY_HDRI = "/hdri/sky_day_2k.hdr";

/** Sky HDRI as the visible background (outside the windows, over the terrace). */
export function SkyBackground({ evening }: { evening: boolean }) {
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    let tex: THREE.DataTexture | null = null;
    let cancelled = false;
    new HDRLoader().load(SKY_HDRI, (t) => {
      if (cancelled) return t.dispose();
      t.mapping = THREE.EquirectangularReflectionMapping;
      tex = t;
      scene.background = t;
      scene.backgroundIntensity = evening ? 0.06 : 0.85;
      scene.backgroundBlurriness = 0.02;
    });
    return () => {
      cancelled = true;
      if (scene.background === tex) scene.background = null;
      tex?.dispose();
    };
  }, [scene, evening]);
  return null;
}

/** The post stack. `quality` picks a cheaper AO preset on weaker GPUs. */
export function Effects({ evening, quality }: { evening: boolean; quality: "high" | "low" }) {
  return (
    <EffectComposer multisampling={0} frameBufferType={THREE.HalfFloatType}>
      <N8AO
        aoRadius={0.9}
        distanceFalloff={0.6}
        intensity={evening ? 2.2 : 3.2}
        quality={quality === "high" ? "medium" : "performance"}
        // NB: halfRes crashes with three r18x render targets (n8ao setupRenderTarget) — keep full res
        color={new THREE.Color("#1a120c")}
      />
      <Bloom mipmapBlur luminanceThreshold={1.1} luminanceSmoothing={0.2} intensity={evening ? 0.55 : 0.35} radius={0.65} />
      <ToneMapping mode={ToneMappingMode.AGX} />
      <HueSaturation saturation={0.08} />
      <BrightnessContrast contrast={0.06} />
      <Vignette offset={0.32} darkness={0.42} />
      <SMAA />
    </EffectComposer>
  );
}

/**
 * Swap mirror meshes for planar reflectors. The kit builds a mirror as a thin slab on a wall; we put a
 * reflecting plane on its room-side face (the side that is NOT backed by geometry within a few cm).
 */
export function upgradeMirrors(root: THREE.Object3D, mirrors: THREE.Mesh[]): THREE.Object3D[] {
  root.updateMatrixWorld(true);
  const added: THREE.Object3D[] = [];
  const ray = new THREE.Raycaster();
  const others: THREE.Object3D[] = [];
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh && !mirrors.includes(o as THREE.Mesh)) others.push(o);
  });
  for (const m of mirrors) {
    const box = new THREE.Box3().setFromObject(m);
    const size = box.getSize(new THREE.Vector3());
    const c = box.getCenter(new THREE.Vector3());
    if (size.y < 0.15) continue;
    const thinX = size.x < size.z;
    const width = thinX ? size.z : size.x;
    if (width < 0.15) continue;
    // which side faces the room: the one without a wall right behind it
    const dir = thinX ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 0, 1);
    // the wall is the NEAREST surface behind the slab; the room side is open for much longer
    ray.far = 3;
    const hitDist = (d: THREE.Vector3) => {
      ray.set(c, d);
      const prev = new Map<THREE.Material, THREE.Side>();
      for (const o of others) {
        const mt = (o as THREE.Mesh).material as THREE.Material;
        if (!prev.has(mt)) {
          prev.set(mt, mt.side);
          mt.side = THREE.DoubleSide;
        }
      }
      const h = ray.intersectObjects(others, false)[0]?.distance ?? Infinity;
      for (const [mt, sd] of prev) mt.side = sd;
      return h;
    };
    const sign = hitDist(dir) < hitDist(dir.clone().negate()) ? -1 : 1;
    const normal = dir.multiplyScalar(sign);
    const half = (thinX ? size.x : size.z) / 2;
    const geo = new THREE.PlaneGeometry(width, size.y);
    const refl = new Reflector(geo, {
      textureWidth: 1024,
      textureHeight: Math.round((1024 * size.y) / width),
      color: new THREE.Color("#b9bcbc"),
      clipBias: 0.003,
    });
    refl.position.copy(c).addScaledVector(normal, half + 0.002);
    refl.lookAt(refl.position.clone().add(normal));
    refl.name = `mirror_reflector_${added.length}`;
    added.push(refl);
  }
  return added;
}

/* ---------------------------------------------------------------------------------------------- */
/* Light pool: the café has ~60 fixtures (downlights, pendants); three.js can afford ~a dozen.    */
/* A fixed set of real lights (fixed count = no shader recompiles) follows the walker and sits on */
/* the nearest fixtures, fading when it hops, so every room you stand in has its real light pools. */
/* ---------------------------------------------------------------------------------------------- */

export type LightFixture = {
  kind: "spot" | "point";
  pos: THREE.Vector3;
  dir: THREE.Vector3; // spots: unit direction of the beam
  color: THREE.Color;
  intensity: number; // three.js candela, already rescaled for the viewer's exposure
  angle: number;
  penumbra: number;
};

// glTF carries Blender's photometric candela; the viewer's sun is ~3.4 lux, so scale to match.
const SPOT_SCALE = 1 / 18;
const POINT_SCALE = 1 / 160;
const POOL_SPOTS = 10;
const POOL_POINTS = 4;

export function collectLightFixtures(lights: THREE.Light[]): LightFixture[] {
  const out: LightFixture[] = [];
  for (const l of lights) {
    const p = l.getWorldPosition(new THREE.Vector3());
    if ((l as THREE.SpotLight).isSpotLight) {
      const s = l as THREE.SpotLight;
      s.target.updateMatrixWorld(true);
      const t = s.target.getWorldPosition(new THREE.Vector3());
      const dir = t.sub(p).normalize();
      out.push({ kind: "spot", pos: p, dir, color: s.color.clone(), intensity: s.intensity * SPOT_SCALE, angle: Math.min(s.angle, 1.2), penumbra: Math.max(s.penumbra, 0.55) });
    } else if ((l as THREE.PointLight).isPointLight) {
      out.push({ kind: "point", pos: p, dir: new THREE.Vector3(0, -1, 0), color: l.color.clone(), intensity: l.intensity * POINT_SCALE, angle: 0, penumbra: 0 });
    }
  }
  return out;
}

type Slot = { light: THREE.SpotLight | THREE.PointLight; fixture: LightFixture | null; next: LightFixture | null; fade: number };

/** Slots already on a wanted fixture keep it; the others are retargeted to the remaining ones. */
function assignSlots(pool: Slot[], ranked: LightFixture[]) {
  const wanted = new Set(ranked);
  const free: Slot[] = [];
  for (const s of pool) {
    if (s.fixture && wanted.has(s.fixture)) {
      wanted.delete(s.fixture);
      s.next = s.fixture;
    } else free.push(s);
  }
  const rest = [...wanted];
  for (const s of free) s.next = rest.shift() ?? null;
}

export function LightPool({ fixtures, store }: { fixtures: LightFixture[]; store: { evening: boolean } }) {
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const built = useMemo(() => {
    const mk = (kind: "spot" | "point", n: number): Slot[] =>
      Array.from({ length: n }, () => {
        const light = kind === "spot" ? new THREE.SpotLight("#fff", 0, 9, 0.7, 0.6, 2) : new THREE.PointLight("#fff", 0, 6, 2);
        light.castShadow = false;
        return { light, fixture: null, next: null, fade: 0 };
      });
    return { spot: mk("spot", fixtures.some((f) => f.kind === "spot") ? POOL_SPOTS : 0), point: mk("point", fixtures.some((f) => f.kind === "point") ? POOL_POINTS : 0) };
  }, [fixtures]);

  // per-frame mutable state lives in a ref (memo values must stay immutable)
  const state = useRef<{ spot: Slot[]; point: Slot[] } | null>(null);
  useEffect(() => {
    state.current = { spot: built.spot.map((x) => ({ ...x })), point: built.point.map((x) => ({ ...x })) };
    const all = [...built.spot, ...built.point];
    for (const s of all) {
      scene.add(s.light);
      if ((s.light as THREE.SpotLight).isSpotLight) scene.add((s.light as THREE.SpotLight).target);
    }
    return () => {
      for (const s of all) {
        s.light.removeFromParent();
        if ((s.light as THREE.SpotLight).isSpotLight) (s.light as THREE.SpotLight).target.removeFromParent();
        s.light.dispose();
      }
    };
  }, [scene, built]);

  const frame = useRef(0);
  const camPos = useMemo(() => new THREE.Vector3(), []);
  const fwd = useMemo(() => new THREE.Vector3(), []);
  useFrame((_, dt) => {
    const slots = state.current;
    if (!slots) return;
    camera.getWorldPosition(camPos);
    camera.getWorldDirection(fwd);
    if (frame.current++ % 12 === 0) {
      for (const kind of ["spot", "point"] as const) {
        const pool = slots[kind];
        if (!pool.length) continue;
        // nearest fixtures, lights in front of the viewer count as closer (that's what you see lit)
        const ranked = fixtures
          .filter((f) => f.kind === kind && Math.abs(f.pos.y - camPos.y) < 4)
          .map((f) => {
            const dx = f.pos.x - camPos.x, dz = f.pos.z - camPos.z;
            const d = Math.hypot(dx, dz);
            const ahead = (dx * fwd.x + dz * fwd.z) / (d || 1);
            return { f, score: d * (ahead > 0 ? 0.75 : 1.25) };
          })
          .sort((a, b) => a.score - b.score)
          .slice(0, pool.length)
          .map((r) => r.f);
        assignSlots(pool, ranked);
      }
    }
    const boost = store.evening ? 1.6 : 1;
    for (const s of [...slots.spot, ...slots.point]) {
      if (s.next !== s.fixture) {
        s.fade = Math.max(0, s.fade - dt * 4); // fade out, then hop
        if (s.fade === 0) {
          s.fixture = s.next;
          const f = s.fixture;
          if (f) {
            s.light.position.copy(f.pos);
            s.light.color.copy(f.color);
            if ((s.light as THREE.SpotLight).isSpotLight) {
              const sp = s.light as THREE.SpotLight;
              sp.angle = f.angle;
              sp.penumbra = f.penumbra;
              sp.target.position.copy(f.pos).addScaledVector(f.dir, 3);
              sp.target.updateMatrixWorld();
            }
          }
        }
      } else if (s.fixture) s.fade = Math.min(1, s.fade + dt * 3);
      s.light.intensity = s.fixture ? s.fixture.intensity * s.fade * boost : 0;
    }
  });
  return null;
}

/** Glass must not cast shadows or the sun never gets inside (same rule as the Cycles build). */
export function isGlassLike(mat: THREE.Material): boolean {
  const m = mat as THREE.MeshPhysicalMaterial;
  return (m.transmission ?? 0) > 0.01 || (m.transparent && m.opacity < 0.95) || /glass/i.test(mat.name);
}

const SHEEN = /^(cb_floor|cb_prep_floor|cb_bar_tile|cb_milazza|ceramic|cup|black_gloss|red_gloss)/;

/**
 * Small per-material touches that the glTF export can't express. Returns the material to use (satin
 * surfaces are promoted to MeshPhysicalMaterial so they can carry a clearcoat).
 */
export function tuneMaterial(src: THREE.Material): THREE.Material {
  let mat = src;
  const lname = src.name.toLowerCase();
  if (SHEEN.test(lname) && (src as THREE.MeshStandardMaterial).isMeshStandardMaterial && !(src as THREE.MeshPhysicalMaterial).isMeshPhysicalMaterial) {
    const p = new THREE.MeshPhysicalMaterial();
    THREE.MeshStandardMaterial.prototype.copy.call(p, src as THREE.MeshStandardMaterial);
    p.defines = { STANDARD: "", PHYSICAL: "" };
    mat = p;
  }
  applyTuning(mat);
  return mat;
}

function applyTuning(mat: THREE.Material) {
  const m = mat as THREE.MeshPhysicalMaterial;
  if (!m.isMeshStandardMaterial) return;
  const name = mat.name.toLowerCase();
  if (/^(led|bulb|shade_in|lens|cb_logo_glow)/.test(name)) {
    // emissive strips feed the bloom pass (threshold 1.0 → only lights glow)
    m.emissiveIntensity = Math.max(m.emissiveIntensity, 2.5);
    m.toneMapped = true;
  }
  if (/chrome|mirror|steel|brass/.test(name)) m.envMapIntensity = 1.4;
  if (SHEEN.test(name)) {
    // satin sheen like the Cycles floors: a faint clearcoat picks up window/env highlights
    if (m.isMeshPhysicalMaterial) {
      m.clearcoat = Math.max(m.clearcoat, name.startsWith("cb_floor") ? 0.35 : 0.6);
      m.clearcoatRoughness = name.startsWith("cb_floor") ? 0.25 : 0.12;
    }
  }
  if (isGlassLike(mat)) {
    m.envMapIntensity = 1.2;
    if (m.isMeshPhysicalMaterial && m.transmission > 0) {
      m.thickness = 0.01;
      m.roughness = Math.min(m.roughness, 0.02);
    }
  }
  if (m.map) m.map.anisotropy = 8;
  for (const t of [m.normalMap, m.roughnessMap]) if (t) t.anisotropy = 8;
  m.needsUpdate = true;
}
