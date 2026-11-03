"use client";

import { useEffect, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, PointerLockControls } from "@react-three/drei";
import * as THREE from "three";

export type ViewMode = "orbit" | "walk";

const EYE_HEIGHT = 1.6;
const MOVE_SPEED = 3.2; // m/s

function FirstPerson() {
  const { camera } = useThree();
  const keys = useRef<Record<string, boolean>>({});

  useEffect(() => {
    // drop to eye height when entering walk mode
    camera.position.y = EYE_HEIGHT;
    const down = (e: KeyboardEvent) => {
      keys.current[e.code] = true;
    };
    const up = (e: KeyboardEvent) => {
      keys.current[e.code] = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [camera]);

  useFrame((_, dt) => {
    const step = MOVE_SPEED * Math.min(dt, 0.05);
    const dir = new THREE.Vector3();
    camera.getWorldDirection(dir);
    dir.y = 0;
    if (dir.lengthSq() === 0) return;
    dir.normalize();
    const right = new THREE.Vector3().crossVectors(dir, new THREE.Vector3(0, 1, 0)).normalize();

    const move = new THREE.Vector3();
    if (keys.current["KeyW"] || keys.current["ArrowUp"]) move.add(dir);
    if (keys.current["KeyS"] || keys.current["ArrowDown"]) move.sub(dir);
    if (keys.current["KeyD"] || keys.current["ArrowRight"]) move.add(right);
    if (keys.current["KeyA"] || keys.current["ArrowLeft"]) move.sub(right);

    if (move.lengthSq() > 0) {
      move.normalize().multiplyScalar(step);
      camera.position.add(move);
    }
    camera.position.y = EYE_HEIGHT;
  });

  return <PointerLockControls />;
}

export default function Controls({ mode, target }: { mode: ViewMode; target: [number, number, number] }) {
  if (mode === "walk") return <FirstPerson />;
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
