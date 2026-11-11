"use client";

// Walk through the café Blender built: loads the exported GLB (same world frame as the plan:
// x = planX, y = height, z = -planY) and reuses the walk-tour layer. Collision blocks come from
// the model's own furniture (mesh bounds below head height), walls/doors/rooms from scene.json.

import { Suspense, useEffect, useMemo, useState, type CSSProperties } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import type { CafeScene, Fixture } from "@/types/cafescene";
import { buildTourModel } from "@/lib/tour/model";
import { TourStore } from "@/lib/tour/store";
import WalkController from "./WalkController";
import WalkOverlay, { useTourVersion } from "./WalkOverlay";
import GalleryButtons from "./GalleryOverlay";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { Effects, LightPool, detectQuality, SkyBackground, collectLightFixtures, isGlassLike, tuneMaterial, upgradeMirrors, type LightFixture } from "./Realism";

/** Architecture and lighting objects from cafe_kit never block walking. */
const ARCH_PREFIX = ["floor_", "ceiling_", "wall_", "glass_", "frame_", "mullion_", "skirt_", "downlight", "Sun", "fill_", "PanoCam", "Camera"];


/**
 * Performance: the kit exports ~1,000 small meshes and dozens of lights. three.js draws every mesh
 * separately and shades each against every light, so we (1) lift every light out into a list that a
 * small fixed pool of real lights follows around (LightPool) and (2) merge all static meshes into one
 * mesh per material.
 */
function optimizeModel(root: THREE.Object3D): { group: THREE.Group; fixtures: LightFixture[] } {
  root.updateMatrixWorld(true);
  const lights: THREE.Light[] = [];
  root.traverse((o) => {
    if ((o as THREE.Light).isLight) lights.push(o as THREE.Light);
  });
  const fixtures = collectLightFixtures(lights);
  for (const l of lights) l.removeFromParent();
  // --- meshes: merge by material (+ attribute signature); floors stay identifiable for click-to-walk
  const groups = new Map<string, { mat: THREE.Material; floor: boolean; geoms: THREE.BufferGeometry[] }>();
  const meshes: THREE.Mesh[] = [];
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh);
  });
  // mirrors become planar reflectors (the slab itself stays as the frame/back)
  const mirrors = meshes.filter((m) => /^mirror/i.test(((Array.isArray(m.material) ? m.material[0] : m.material) as THREE.Material).name));
  const reflectors = upgradeMirrors(root, mirrors);
  const tuned = new Map<THREE.Material, THREE.Material>();
  for (const m of meshes) {
    const src = (Array.isArray(m.material) ? m.material[0] : m.material) as THREE.Material;
    let mat = tuned.get(src);
    if (!mat) {
      mat = tuneMaterial(src);
      tuned.set(src, mat);
    }
    const g = m.geometry.clone();
    for (const name of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(name)) g.deleteAttribute(name);
    if (!g.attributes.normal) g.computeVertexNormals();
    if (!g.attributes.uv) g.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array((g.attributes.position.count || 0) * 2), 2));
    g.applyMatrix4(m.matrixWorld);
    const floor = (m.name || "").startsWith("floor_");
    const key = `${mat.uuid}|${floor ? "floor" : "x"}|${g.index ? "i" : "n"}`;
    let entry = groups.get(key);
    if (!entry) {
      entry = { mat, floor, geoms: [] };
      groups.set(key, entry);
    }
    entry.geoms.push(g);
  }
  const out = new THREE.Group();
  for (const { mat, floor, geoms } of groups.values()) {
    const merged = geoms.length === 1 ? geoms[0] : mergeGeometries(geoms, false);
    if (!merged) continue;
    const mesh = new THREE.Mesh(merged, mat);
    mesh.castShadow = !floor && !isGlassLike(mat);
    mesh.receiveShadow = !isGlassLike(mat);
    if (floor) mesh.userData.floor = true;
    out.add(mesh);
  }
  for (const r of reflectors) out.add(r);
  return { group: out, fixtures };
}

function applyRoomEnvironment(gl: THREE.WebGLRenderer, scene: THREE.Scene, intensity: number) {
  const pmrem = new THREE.PMREMGenerator(gl);
  const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = env;
  scene.environmentIntensity = intensity;
  return () => {
    scene.environment = null;
    env.dispose();
    pmrem.dispose();
  };
}

/** Direction toward the sun as designed in Blender (falls back to a high southern sun). */
function sunPosition(root: THREE.Object3D): [number, number, number] {
  let out: [number, number, number] = [-9, 22, 38];
  root.traverse((o) => {
    if ((o as THREE.DirectionalLight).isDirectionalLight) {
      const q = new THREE.Quaternion();
      o.getWorldQuaternion(q);
      const toward = new THREE.Vector3(0, 0, 1).applyQuaternion(q).multiplyScalar(45);
      out = [toward.x, Math.max(toward.y, 10), toward.z];
    }
  });
  return out;
}

function prepareModel(root: THREE.Object3D): Fixture[] {
  root.updateMatrixWorld(true);
  const box = new THREE.Box3();
  const blocks: Fixture[] = [];
  let i = 0;
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    const name = o.name || "";
    if (ARCH_PREFIX.some((p) => name.startsWith(p))) return;
    box.setFromObject(m);
    if (box.isEmpty()) return;
    const w = box.max.x - box.min.x;
    const d = box.max.z - box.min.z;
    const h = box.max.y - box.min.y;
    if (box.min.y > 1.15 || box.max.y < 0.12) return; // above head height, or flat on the floor
    if (w > 9 || d > 9 || w < 0.03 || d < 0.03) return;
    blocks.push({
      id: `glb_${i++}`,
      name,
      category: "generic",
      position: [(box.min.x + box.max.x) / 2, -(box.min.z + box.max.z) / 2],
      rotation: 0,
      footprint: [w, d],
      height: h,
      baseHeight: box.min.y,
      placedBy: "design",
      confidence: 1,
      source: { system: 3, method: "reconstruction" },
    });
  });
  return blocks;
}

/** Dev only: expose renderer stats so a headless check can confirm the merge worked. */
function DevStats({ model }: { model: THREE.Group }) {
  const gl = useThree((s) => s.gl);
  useFrame(() => {
    if (process.env.NODE_ENV === "production") return;
    const w = window as unknown as { __cafeStats?: Record<string, number>; __cafeModel?: THREE.Group };
    w.__cafeModel = model;
    w.__cafeStats = {
      calls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      meshes: model.children.filter((c) => (c as THREE.Mesh).isMesh).length,
      lights: model.children.filter((c) => (c as THREE.Light).isLight).length,
    };
  });
  return null;
}

/** Soft studio-like reflections so metal, marble and glass read as real materials instead of going black. */
function Reflections({ evening }: { evening: boolean }) {
  const { gl, scene } = useThree();
  useEffect(() => applyRoomEnvironment(gl, scene, evening ? 0.2 : 0.5), [gl, scene, evening]);
  return null;
}

function SceneLights({ store, sun, radius, shadowMap }: { store: TourStore; sun: [number, number, number]; radius: number; shadowMap: number }) {
  useTourVersion(store);
  const ev = store.evening;
  const r = Math.min(Math.max(radius, 10), 60);
  return (
    <>
      <ambientLight intensity={ev ? 0.04 : 0.08} color="#ffe9d2" />
      <hemisphereLight color={ev ? "#6f7aa0" : "#eef0f2"} groundColor="#a07c58" intensity={ev ? 0.12 : 0.34} />
      <directionalLight
        position={ev ? [-30, 7, 30] : sun}
        intensity={ev ? 0.3 : 3.4}
        color={ev ? "#ffa86a" : "#fff1de"}
        castShadow
        shadow-mapSize-width={shadowMap}
        shadow-mapSize-height={shadowMap}
        shadow-camera-left={-r}
        shadow-camera-right={r}
        shadow-camera-top={r}
        shadow-camera-bottom={-r}
        shadow-camera-near={1}
        shadow-camera-far={150}
        shadow-bias={-0.0003}
        shadow-normalBias={0.025}
        shadow-radius={4}
      />
    </>
  );
}

function Inner({ glbUrl, scene, projectName, onExit }: { glbUrl: string; scene: CafeScene; projectName: string; onExit?: () => void }) {
  const gltf = useGLTF(glbUrl);
  const designId = glbUrl.match(/blender-designs\/([^/]+)\//)?.[1];
  // effects tier chosen once at load (Realism.detectQuality)
  const [quality] = useState(detectQuality);
  const { store, model, sun, radius, fixtures } = useMemo(() => {
    const sun = sunPosition(gltf.scene);
    const bounds = new THREE.Box3().setFromObject(gltf.scene);
    const radius = bounds.isEmpty() ? 25 : bounds.getSize(new THREE.Vector3()).setY(0).length() / 2 + 2;
    const blocks = prepareModel(gltf.scene);
    const synthetic: CafeScene = { ...scene, fixtures: blocks };
    const { group: model, fixtures } = optimizeModel(gltf.scene);
    return { store: new TourStore(buildTourModel(synthetic)), model, sun, radius, fixtures };
  }, [gltf, scene]);
  useEffect(() => () => store.dispose(), [store]);
  useTourVersion(store);
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") (window as unknown as { __tour?: TourStore }).__tour = store;
  }, [store]);

  return (
    <>
      <Canvas
        shadows
        dpr={quality === "high" ? [1, 1.5] : [1, 1]}
        gl={{ antialias: false, powerPreference: "high-performance", stencil: false }}
        flat
        onCreated={({ gl }) => {
          // tone mapping happens in the post stack (AgX, like the Cycles renders)
          gl.toneMapping = THREE.NoToneMapping;
          gl.shadowMap.type = THREE.PCFShadowMap; // r18x: PCF honours shadow.radius (PCFSoft was removed)
        }}
      >
        <Reflections evening={store.evening} />
        <SkyBackground evening={store.evening} />
        <SceneLights store={store} sun={sun} radius={radius} shadowMap={quality === "high" ? 4096 : 2048} />
        <primitive object={model} />
        <LightPool fixtures={fixtures} store={store} />
        <DevStats model={model} />
        <WalkController store={store} />
        {!(typeof window !== "undefined" && window.location.search.includes("fx=0")) && <Effects evening={store.evening} quality={quality} />}
      </Canvas>
      <WalkOverlay
        store={store}
        projectName={projectName}
        subtitle="AI design · built in Blender · walkable model"
        onExit={onExit}
        extraActions={designId ? (style) => <GalleryButtons designId={designId} projectName={projectName} buttonStyle={style} /> : undefined}
      />
    </>
  );
}

export default function BlenderWalkViewer({ glbUrl, sceneUrl, projectName, onExit }: { glbUrl: string; sceneUrl: string; projectName: string; onExit?: () => void }) {
  const [scene, setScene] = useState<CafeScene | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    fetch(sceneUrl)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`scene.json ${r.status}`))))
      .then((s) => setScene(s as CafeScene))
      .catch((e) => setErr(e instanceof Error ? e.message : "Could not load the plan"));
  }, [sceneUrl]);

  return (
    <div style={S.wrap}>
      {err && <div style={S.loading}>{err}</div>}
      {!err && !scene && <div style={S.loading}>Loading the plan…</div>}
      {scene && (
        <Suspense fallback={<div style={S.loading}>Loading the 3D model…</div>}>
          <Inner glbUrl={glbUrl} scene={scene} projectName={projectName} onExit={onExit} />
        </Suspense>
      )}
    </div>
  );
}

const S: Record<string, CSSProperties> = {
  wrap: { position: "absolute", inset: 0, background: "#1c1511", overflow: "hidden" },
  loading: { position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#f3ece0", fontFamily: "system-ui, sans-serif", fontSize: 15 },
};
