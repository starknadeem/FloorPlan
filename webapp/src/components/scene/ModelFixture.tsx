"use client";

import { useMemo } from "react";
import * as THREE from "three";
import { useGLTF } from "@react-three/drei";
import type { Vec2 } from "@/types/cafescene";
import type { ModelDef } from "@/lib/design/models";

// Measure each model's bounding box once (expensive on high-poly models), then reuse across instances.
const dimCache = new Map<string, { size: THREE.Vector3; min: THREE.Vector3; center: THREE.Vector3 }>();

/**
 * Loads a glb model, scales it to the fixture footprint, sits it on the floor (y=0), and centers it.
 * The parent group applies world position + the fixture's rotation; this adds the model's base rotation.
 */
export default function ModelFixture({
  def,
  footprint,
}: {
  def: ModelDef;
  footprint: Vec2;
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
  }, [scene, footprint, def]);

  return <primitive object={object} />;
}
