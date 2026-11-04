"use client";

import type { CafeScene } from "@/types/cafescene";
import type { StylePalette } from "@/lib/design/palette";

export default function Lights({ scene, pal, evening = false }: { scene: CafeScene; pal: StylePalette; evening?: boolean }) {
  const L = pal.light;
  const pendants = (scene.lights ?? []).filter((l) => l.type === "pendant" || l.type === "point");
  // Evening: a low amber sun, cool dim sky light, and the pendants carry the room.
  const ambient = evening ? L.ambient * 0.35 : L.ambient;
  const hemi = evening ? 0.14 : L.hemi;
  const hemiSky = evening ? "#6f7aa0" : L.hemiSky;
  const dir = evening ? 0.35 : L.dir;
  const dirColor = evening ? "#ffa86a" : L.dirColor;
  const dirPos: [number, number, number] = evening ? [-30, 7, 30] : [14, 18, 10];
  const pendMul = evening ? 2.0 : 1;

  return (
    <group>
      <ambientLight intensity={ambient} />
      <hemisphereLight color={hemiSky} groundColor={L.hemiGround} intensity={hemi} />

      <directionalLight
        position={dirPos}
        intensity={dir}
        color={dirColor}
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
          intensity={(l.intensity ?? L.pendantI) * pendMul}
          distance={7}
          decay={2}
          color={L.pendant}
          castShadow={false}
        />
      ))}
    </group>
  );
}
