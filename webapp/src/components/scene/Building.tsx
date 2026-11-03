"use client";

import { useMemo } from "react";
import * as THREE from "three";
import type { CafeScene, Room, Wall } from "@/types/cafescene";
import { buildWallBoxes, roomShape, wallAngleY } from "@/lib/geometry";
import type { StylePalette } from "@/lib/design/palette";
import { stoneTexture } from "@/lib/design/textures";

/** Lighten/darken a hex color by a factor (1 = unchanged). */
function shade(hex: string, f: number): string {
  const c = new THREE.Color(hex);
  c.multiplyScalar(f);
  return `#${c.getHexString()}`;
}

function WallMesh({ wall, scene, pal }: { wall: Wall; scene: CafeScene; pal: StylePalette }) {
  const { boxes, glass } = useMemo(() => buildWallBoxes(wall, scene.openings), [wall, scene.openings]);
  const angle = wallAngleY(wall.a, wall.b);
  const color = wall.exterior ? pal.wall : shade(pal.wall, 1.05);
  const base = wall.baseHeight ?? 0;

  return (
    <group position={[wall.a[0], base, -wall.a[1]]} rotation={[0, angle, 0]}>
      {boxes.map((b, i) => (
        <mesh key={`b${i}`} position={[b.u, b.yCenter, 0]} castShadow receiveShadow>
          <boxGeometry args={[b.length, b.height, wall.thickness]} />
          <meshStandardMaterial color={color} roughness={0.92} metalness={0} />
        </mesh>
      ))}
      {glass.map((g, i) => (
        <mesh key={`g${i}`} position={[g.u, g.yCenter, 0]}>
          <boxGeometry args={[g.width, g.height, 0.03]} />
          <meshStandardMaterial color={pal.glass} transparent opacity={0.25} roughness={0.1} metalness={0.1} />
        </mesh>
      ))}
    </group>
  );
}

function RoomSurfaces({ room, pal }: { room: Room; pal: StylePalette }) {
  const geom = useMemo(() => new THREE.ShapeGeometry(roomShape(room.polygon)), [room.polygon]);
  const outdoor = room.category === "seating_outdoor";
  const floorColor = outdoor ? pal.floorOutdoor : pal.floor;
  const floorTex = useMemo(() => stoneTexture(floorColor), [floorColor]);

  return (
    <group>
      <mesh geometry={geom} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow>
        <meshStandardMaterial map={floorTex} color="#ffffff" roughness={0.95} metalness={0} side={THREE.DoubleSide} />
      </mesh>
      {room.ceilingHeight > 0 && (
        <mesh geometry={geom} rotation={[-Math.PI / 2, 0, 0]} position={[0, room.ceilingHeight, 0]}>
          <meshStandardMaterial color={pal.ceiling} roughness={0.95} metalness={0} side={THREE.DoubleSide} />
        </mesh>
      )}
    </group>
  );
}

export default function Building({ scene, pal }: { scene: CafeScene; pal: StylePalette }) {
  return (
    <group>
      {scene.rooms.map((r) => (
        <RoomSurfaces key={r.id} room={r} pal={pal} />
      ))}
      {scene.walls.map((w) => (
        <WallMesh key={w.id} wall={w} scene={scene} pal={pal} />
      ))}
    </group>
  );
}
