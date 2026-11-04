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

/** Architecture and lighting objects from cafe_kit never block walking. */
const ARCH_PREFIX = ["floor_", "ceiling_", "wall_", "glass_", "frame_", "mullion_", "skirt_", "downlight", "Sun", "fill_", "PanoCam", "Camera"];

const MAX_LIGHTS = 8;

/**
 * Performance: the kit exports ~1,000 small meshes and dozens of lights. three.js draws every mesh
 * separately and shades each against every light, so we (1) keep only a few of the strongest
 * point lights (pendants) and (2) merge all static meshes into one mesh per material.
 */
function optimizeModel(root: THREE.Object3D): THREE.Group {
  root.updateMatrixWorld(true);
  // --- lights: keep a few points, drop spots/suns (our own sun + emissive strips carry the rest)
  const lights: THREE.Light[] = [];
  root.traverse((o) => {
    if ((o as THREE.Light).isLight) lights.push(o as THREE.Light);
  });
  const points = lights.filter((l) => (l as THREE.PointLight).isPointLight);
  const keep = new Set<THREE.Light>();
  // spread the kept lights out: pick by a coarse spatial hash so one room doesn't take them all
  const seen = new Set<string>();
  for (const l of points) {
    const p = new THREE.Vector3();
    l.getWorldPosition(p);
    const key = `${Math.round(p.x / 3)}:${Math.round(p.z / 3)}`;
    if (seen.has(key)) continue;
    seen.add(key);
    keep.add(l);
    if (keep.size >= MAX_LIGHTS) break;
  }
  for (const l of lights) {
    if (!keep.has(l)) {
      l.removeFromParent();
      continue;
    }
    l.castShadow = false;
    l.intensity = 5;
    (l as THREE.PointLight).distance = 7;
    (l as THREE.PointLight).decay = 2;
  }
  // --- meshes: merge by material (+ attribute signature); floors stay identifiable for click-to-walk
  const groups = new Map<string, { mat: THREE.Material; floor: boolean; geoms: THREE.BufferGeometry[] }>();
  const meshes: THREE.Mesh[] = [];
  root.traverse((o) => {
    if ((o as THREE.Mesh).isMesh) meshes.push(o as THREE.Mesh);
  });
  for (const m of meshes) {
    const mat = (Array.isArray(m.material) ? m.material[0] : m.material) as THREE.Material;
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
    mesh.castShadow = !floor;
    mesh.receiveShadow = true;
    if (floor) mesh.userData.floor = true;
    out.add(mesh);
  }
  for (const l of keep) out.add(l);
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
    const w = window as unknown as { __cafeStats?: Record<string, number> };
    w.__cafeStats = {
      calls: gl.info.render.calls,
      triangles: gl.info.render.triangles,
      meshes: model.children.filter((c) => (c as THREE.Mesh).isMesh).length,
      lights: model.children.filter((c) => (c as THREE.Light).isLight).length,
    };
  });
  return null;
}

function SceneLights({ store }: { store: TourStore }) {
  useTourVersion(store);
  const ev = store.evening;
  return (
    <>
      <ambientLight intensity={ev ? 0.1 : 0.38} />
      <hemisphereLight color={ev ? "#6f7aa0" : "#fff1dc"} groundColor="#7a6a58" intensity={ev ? 0.15 : 0.7} />
      <directionalLight
        position={ev ? [-30, 7, 30] : [-9, 22, 38]}
        intensity={ev ? 0.3 : 2.0}
        color={ev ? "#ffa86a" : "#fff0da"}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-25}
        shadow-camera-right={25}
        shadow-camera-top={25}
        shadow-camera-bottom={-25}
        shadow-camera-near={1}
        shadow-camera-far={120}
        shadow-bias={-0.0004}
        shadow-normalBias={0.03}
      />
    </>
  );
}

function Inner({ glbUrl, scene, projectName, onExit }: { glbUrl: string; scene: CafeScene; projectName: string; onExit?: () => void }) {
  const gltf = useGLTF(glbUrl);
  const { store, model } = useMemo(() => {
    const blocks = prepareModel(gltf.scene);
    const synthetic: CafeScene = { ...scene, fixtures: blocks };
    const model = optimizeModel(gltf.scene);
    return { store: new TourStore(buildTourModel(synthetic)), model };
  }, [gltf, scene]);
  useEffect(() => () => store.dispose(), [store]);

  return (
    <>
      <Canvas
        shadows
        dpr={[1, 1.25]}
        gl={{ antialias: true }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.15;
          gl.shadowMap.type = THREE.PCFSoftShadowMap;
        }}
      >
        <SceneLights store={store} />
        <primitive object={model} />
        <DevStats model={model} />
        <WalkController store={store} />
      </Canvas>
      <WalkOverlay store={store} projectName={projectName} subtitle="AI design · built in Blender · walkable model" onExit={onExit} />
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
