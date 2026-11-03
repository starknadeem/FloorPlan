"use client";

import { Suspense, useEffect, type RefObject } from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { Environment, Lightformer } from "@react-three/drei";
import * as THREE from "three";
import type { CafeScene, Fixture } from "@/types/cafescene";
import Building from "./Building";
import Fixtures from "./Fixtures";
import Lights from "./Lights";
import Controls, { type ViewMode } from "./Controls";
import { frameScene } from "@/lib/geometry";
import { resolvePalette } from "@/lib/design/palette";

export interface CaptureApi {
  capture: () => string | null;
  isometric: () => void;
  reset: () => void;
  /** Current camera pose in three.js WORLD coords, for the Blender render route. */
  cameraPose: () => { position: [number, number, number]; target: [number, number, number] };
}

function Ground({ center, color }: { center: [number, number, number]; color: string }) {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[center[0], -0.02, center[2]]} receiveShadow>
      <planeGeometry args={[300, 300]} />
      <meshStandardMaterial color={color} roughness={1} metalness={0} />
    </mesh>
  );
}

function CaptureController({
  apiRef,
  center,
  span,
  defaultCam,
  defaultTarget,
}: {
  apiRef: RefObject<CaptureApi | null>;
  center: [number, number, number];
  span: number;
  defaultCam: [number, number, number];
  defaultTarget: [number, number, number];
}) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as { target?: THREE.Vector3; update?: () => void } | null;

  useEffect(() => {
    apiRef.current = {
      capture: () => {
        gl.render(scene, camera);
        return gl.domElement.toDataURL("image/png");
      },
      isometric: () => {
        const d = span * 0.95;
        camera.position.set(center[0] + d, span * 1.25 + 3, center[2] + d);
        if (controls?.target) {
          controls.target.set(center[0], 0.5, center[2]);
          controls.update?.();
        } else {
          camera.lookAt(center[0], 0.5, center[2]);
        }
      },
      reset: () => {
        camera.position.set(...defaultCam);
        if (controls?.target) {
          controls.target.set(...defaultTarget);
          controls.update?.();
        } else {
          camera.lookAt(...defaultTarget);
        }
      },
      cameraPose: () => {
        const t = controls?.target ?? new THREE.Vector3(...defaultTarget);
        return {
          position: [camera.position.x, camera.position.y, camera.position.z],
          target: [t.x, t.y, t.z],
        };
      },
    };
  }, [gl, scene, camera, controls, center, span, defaultCam, defaultTarget, apiRef]);

  return null;
}

export default function CafeCanvas({
  scene,
  mode,
  selectedId,
  onSelect,
  captureApi,
}: {
  scene: CafeScene;
  mode: ViewMode;
  selectedId: string | null;
  onSelect: (f: Fixture | null) => void;
  captureApi?: RefObject<CaptureApi | null>;
}) {
  const { target, camera, center, span } = frameScene({ walls: scene.walls, rooms: scene.rooms });
  const pal = resolvePalette(scene);
  const bg = pal.light.bg;

  return (
    <Canvas
      shadows
      dpr={[1, 2]}
      camera={{ position: camera, fov: 52, near: 0.1, far: 500 }}
      gl={{ antialias: true, preserveDrawingBuffer: true }}
      onPointerMissed={() => onSelect(null)}
      onCreated={({ gl, scene: s }) => {
        gl.toneMapping = THREE.ACESFilmicToneMapping;
        gl.toneMappingExposure = 1.1;
        gl.shadowMap.type = THREE.PCFSoftShadowMap;
        s.background = new THREE.Color(bg);
        s.fog = new THREE.Fog(bg, 50, 120);
      }}
    >
      <Suspense fallback={null}>
        <Lights scene={scene} pal={pal} />
        <Environment resolution={128}>
          <Lightformer form="rect" intensity={1.6} position={[0, 8, 0]} scale={[14, 14, 1]} rotation={[-Math.PI / 2, 0, 0]} color={pal.light.hemiSky} />
          <Lightformer form="rect" intensity={0.9} position={[8, 3, 6]} scale={[8, 8, 1]} color="#ffffff" />
          <Lightformer form="rect" intensity={0.7} position={[-8, 3, -6]} scale={[8, 8, 1]} color={pal.light.pendant} />
        </Environment>
        <Ground center={target} color={pal.floorOutdoor} />
        <Building scene={scene} pal={pal} />
        <Fixtures scene={scene} pal={pal} selectedId={selectedId} onSelect={onSelect} />
      </Suspense>
      <Controls mode={mode} target={target} />
      {captureApi && (
        <CaptureController apiRef={captureApi} center={center} span={span} defaultCam={camera} defaultTarget={target} />
      )}
    </Canvas>
  );
}
