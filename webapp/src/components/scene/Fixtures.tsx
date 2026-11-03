"use client";

import { useState } from "react";
import * as THREE from "three";
import type { CafeScene, Fixture } from "@/types/cafescene";
import { fixtureHeight } from "@/lib/geometry";
import type { StylePalette } from "@/lib/design/palette";
import FurnitureModel from "./FurnitureModels";

function FixtureItem({
  f,
  pal,
  selected,
  onSelect,
}: {
  f: Fixture;
  pal: StylePalette;
  selected: boolean;
  onSelect: (f: Fixture | null) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const h = fixtureHeight(f);
  const base = f.baseHeight ?? 0;
  const [w, d] = f.footprint;

  return (
    <group
      position={[f.position[0], base, -f.position[1]]}
      rotation={[0, THREE.MathUtils.degToRad(-f.rotation), 0]}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(f);
      }}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        setHovered(false);
        document.body.style.cursor = "auto";
      }}
    >
      <FurnitureModel f={f} pal={pal} />

      {/* transparent hit box covering the whole footprint for easy selection */}
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[Math.max(w, 0.1), Math.max(h, 0.1), Math.max(d, 0.1)]} />
        <meshBasicMaterial transparent opacity={0} depthWrite={false} />
      </mesh>

      {(selected || hovered) && (
        <mesh position={[0, h / 2, 0]}>
          <boxGeometry args={[w + 0.06, h + 0.06, d + 0.06]} />
          <meshBasicMaterial color={selected ? "#ffcf66" : "#ffe4a0"} wireframe />
        </mesh>
      )}
    </group>
  );
}

export default function Fixtures({
  scene,
  pal,
  selectedId,
  onSelect,
}: {
  scene: CafeScene;
  pal: StylePalette;
  selectedId: string | null;
  onSelect: (f: Fixture | null) => void;
}) {
  return (
    <group>
      {scene.fixtures.map((f) => (
        <FixtureItem key={f.id} f={f} pal={pal} selected={f.id === selectedId} onSelect={onSelect} />
      ))}
    </group>
  );
}
