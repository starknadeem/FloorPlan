"use client";

import { OrbitControls } from "@react-three/drei";

/** "orbit" = inspect/edit camera; "walk" = first-person tour (see tour/WalkController). */
export type ViewMode = "orbit" | "walk";

export default function Controls({ target }: { target: [number, number, number] }) {
  return (
    <OrbitControls
      makeDefault
      target={target}
      enableDamping
      dampingFactor={0.08}
      maxPolarAngle={Math.PI / 2.05}
      minDistance={2}
      maxDistance={40}
    />
  );
}
