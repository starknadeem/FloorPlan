"use client";

import type { CafeScene } from "@/types/cafescene";
import type { StylePalette } from "@/lib/design/palette";

export default function Lights({ scene, pal }: { scene: CafeScene; pal: StylePalette }) {
  const L = pal.light;
  const pendants = (scene.lights ?? []).filter((l) => l.type === "pendant" || l.type === "point");

  return (
    <group>
      <ambientLight intensity={L.ambient} />
      <hemisphereLight color={L.hemiSky} groundColor={L.hemiGround} intensity={L.hemi} />

      <directionalLight
        position={[14, 18, 10]}
        intensity={L.dir}
        color={L.dirColor}
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={0.5}
        shadow-camera-far={90}
        shadow-camera-left={-30}
        shadow-camera-right={30}
        shadow-camera-top={30}
        shadow-camera-bottom={-30}
        shadow-bias={-0.0004}
      />

      {pendants.map((l) => (
        <pointLight
          key={l.id}
          position={[l.position?.[0] ?? 0, l.mountHeight ?? 2.2, -(l.position?.[1] ?? 0)]}
          intensity={l.intensity ?? L.pendantI}
          distance={7}
          decay={2}
          color={L.pendant}
          castShadow={false}
        />
      ))}
    </group>
  );
}
