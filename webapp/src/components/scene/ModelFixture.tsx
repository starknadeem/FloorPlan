"use client";

import { useMemo } from "react";
import * as THREE from "three";
import { useGLTF } from "@react-three/drei";
import type { FixtureCategory, Vec2 } from "@/types/cafescene";
import type { ModelDef } from "@/lib/design/models";

// Measure each model's bounding box once (expensive on high-poly models), then reuse across instances.
const dimCache = new Map<string, { size: THREE.Vector3; min: THREE.Vector3; center: THREE.Vector3 }>();

const SEATING = new Set<FixtureCategory>(["chair", "stool", "sofa", "banquette"]);
const APPLIANCE = new Set<FixtureCategory>([
  "fridge", "freezer", "ice_maker", "oven", "dishwasher", "sink", "espresso_machine", "grinder", "blender", "mixer",
]);
const CREAM = new THREE.Color("#d9d2c4"); // on-brand upholstery
const _hsl = { h: 0, s: 0, l: 0 };

/**
 * Nudge Kenney's flat palette toward the Coffee Berry look: recolor bright/warm seat cushions to a
 * neutral cream, give appliance metal a stainless feel, and let everything catch the environment.
 */
function enhanceMaterials(root: THREE.Object3D, category?: FixtureCategory) {
  root.traverse((o) => {
    const m = o as THREE.Mesh;
    if (!m.isMesh) return;
    const mats = Array.isArray(m.material) ? m.material : [m.material];
    for (const mat of mats) {
      const std = mat as THREE.MeshStandardMaterial;
      if (!std || !std.color) continue;
      std.envMapIntensity = 1.1;
      std.color.getHSL(_hsl);
      if (category && SEATING.has(category)) {
        // bright warm cushion (salmon/pink/orange) → cream; leave dark wood frames alone
        if (_hsl.s > 0.28 && _hsl.l > 0.42 && (_hsl.h < 0.11 || _hsl.h > 0.94)) {
          std.color.copy(CREAM);
          std.roughness = Math.min(std.roughness ?? 0.8, 0.85);
        }
      } else if (category && APPLIANCE.has(category)) {
        // neutral grey metal bodies → stainless
        if (_hsl.s < 0.12 && _hsl.l > 0.3 && _hsl.l < 0.85) {
          std.metalness = 0.75;
          std.roughness = 0.35;
        }
      }
      std.needsUpdate = true;
    }
  });
}

/**
 * Loads a glb model, scales it to the fixture footprint, sits it on the floor (y=0), and centers it.
 * The parent group applies world position + the fixture's rotation; this adds the model's base rotation.
 */
export default function ModelFixture({
  def,
  footprint,
  category,
}: {
  def: ModelDef;
  footprint: Vec2;
  category?: FixtureCategory;
}) {
  const { scene } = useGLTF(def.url);

  const object = useMemo(() => {
    let dim = dimCache.get(def.url);
    if (!dim) {
      const box = new THREE.Box3().setFromObject(scene);
      const size = new THREE.Vector3();
      const center = new THREE.Vector3();
      box.getSize(size);
      box.getCenter(center);
      dim = { size, min: box.min.clone(), center };
      dimCache.set(def.url, dim);
    }

    const clone = scene.clone(true);
    clone.traverse((o) => {
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        m.castShadow = true;
        m.receiveShadow = true;
      }
    });
    enhanceMaterials(clone, category);

    // center on x/z, drop base to y=0 (in model units)
    clone.position.set(-dim.center.x, -dim.min.y, -dim.center.z);

    const targetW = Math.max(footprint[0], 0.1);
    const targetD = Math.max(footprint[1], 0.1);
    const sW = dim.size.x > 1e-3 ? targetW / dim.size.x : 1;
    const sD = dim.size.z > 1e-3 ? targetD / dim.size.z : 1;
    const scale = def.fit === "contain" ? Math.min(sW, sD) : sW;

    const g = new THREE.Group();
    g.add(clone);
    g.scale.setScalar(scale);
    g.rotation.y = THREE.MathUtils.degToRad(def.baseRotationDeg ?? 0);
    return g;
  }, [scene, footprint, def, category]);

  return <primitive object={object} />;
}
