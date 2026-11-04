"use client";

import { useMemo } from "react";
import * as THREE from "three";
import type { CafeScene, Room, Wall } from "@/types/cafescene";
import { buildWallBoxes, pointInPolygon, roomShape, wallAngleY } from "@/lib/geometry";
import type { StylePalette } from "@/lib/design/palette";
import { pbr } from "@/lib/design/textures";

/** Lighten/darken a hex color by a factor (1 = unchanged). */
function shade(hex: string, f: number): string {
  const c = new THREE.Color(hex);
  c.multiplyScalar(f);
  return `#${c.getHexString()}`;
}

const r2 = (n: number) => Math.round(n * 100) / 100;

/** One wall box skinned with tiled plaster PBR, tinted by the palette wall colour. */
function WallBox({
  b,
  thickness,
  color,
}: {
  b: { u: number; yCenter: number; length: number; height: number };
  thickness: number;
  color: string;
}) {
  // plaster texture is ~3 m; tile per box so the grain stays life-sized.
  const rx = Math.max(0.3, r2(b.length / 3));
  const ry = Math.max(0.3, r2(b.height / 3));
  const m = pbr("plaster", rx, ry);
  return (
    <mesh position={[b.u, b.yCenter, 0]} castShadow receiveShadow>
      <boxGeometry args={[b.length, b.height, thickness]} />
      <meshStandardMaterial
        map={m.map}
        normalMap={m.normalMap}
        roughnessMap={m.roughnessMap}
        color={color}
        roughness={1}
        metalness={0}
      />
    </mesh>
  );
}

/** A window: glass pane + dark frame + vertical mullions, so a glazed storefront still reads as a wall. */
function GlazedOpening({
  g,
  thickness,
  pal,
}: {
  g: { u: number; yCenter: number; width: number; height: number };
  thickness: number;
  pal: StylePalette;
}) {
  const bar = 0.06;
  const depth = thickness + 0.02;
  const frame = "#2b2b2b";
  const mullions: number[] = [];
  for (let x = 1.0; x < g.width - 0.3; x += 1.0) mullions.push(-g.width / 2 + x);
  return (
    <group position={[g.u, g.yCenter, 0]}>
      <mesh>
        <boxGeometry args={[g.width, g.height, 0.02]} />
        <meshStandardMaterial color={pal.glass} transparent opacity={0.28} roughness={0.08} metalness={0.1} />
      </mesh>
      {/* frame: top, bottom, left, right */}
      <mesh position={[0, g.height / 2 - bar / 2, 0]}><boxGeometry args={[g.width, bar, depth]} /><meshStandardMaterial color={frame} roughness={0.6} /></mesh>
      <mesh position={[0, -g.height / 2 + bar / 2, 0]}><boxGeometry args={[g.width, bar, depth]} /><meshStandardMaterial color={frame} roughness={0.6} /></mesh>
      <mesh position={[-g.width / 2 + bar / 2, 0, 0]}><boxGeometry args={[bar, g.height, depth]} /><meshStandardMaterial color={frame} roughness={0.6} /></mesh>
      <mesh position={[g.width / 2 - bar / 2, 0, 0]}><boxGeometry args={[bar, g.height, depth]} /><meshStandardMaterial color={frame} roughness={0.6} /></mesh>
      {mullions.map((x, i) => (
        <mesh key={i} position={[x, 0, 0]}><boxGeometry args={[bar * 0.7, g.height, depth]} /><meshStandardMaterial color={frame} roughness={0.6} /></mesh>
      ))}
    </group>
  );
}

function WallMesh({ wall, scene, pal }: { wall: Wall; scene: CafeScene; pal: StylePalette }) {
  const { boxes, glass } = useMemo(() => buildWallBoxes(wall, scene.openings), [wall, scene.openings]);
  const angle = wallAngleY(wall.a, wall.b);
  const color = wall.exterior ? pal.wall : shade(pal.wall, 1.05);
  const base = wall.baseHeight ?? 0;

  const solids = boxes.filter((b) => b.kind === "solid");
  return (
    <group position={[wall.a[0], base, -wall.a[1]]} rotation={[0, angle, 0]}>
      {boxes.map((b, i) => (
        <WallBox key={`b${i}`} b={b} thickness={wall.thickness} color={color} />
      ))}
      {/* skirting / baseboard along the foot of each solid wall run */}
      {solids.map((b, i) => (
        <mesh key={`sk${i}`} position={[b.u, 0.06, 0]} castShadow receiveShadow>
          <boxGeometry args={[b.length, 0.12, wall.thickness + 0.02]} />
          <meshStandardMaterial color={shade(pal.wall, 0.55)} roughness={0.7} metalness={0} />
        </mesh>
      ))}
      {glass.map((g, i) => (
        <GlazedOpening key={`g${i}`} g={g} thickness={wall.thickness} pal={pal} />
      ))}
    </group>
  );
}

function RoomSurfaces({ room, pal }: { room: Room; pal: StylePalette }) {
  const geom = useMemo(() => new THREE.ShapeGeometry(roomShape(room.polygon)), [room.polygon]);
  const outdoor = room.category === "seating_outdoor";
  // grid of recessed ceiling downlights inside the room footprint
  const downlights = useMemo(() => {
    if (room.ceilingHeight <= 0) return [] as [number, number, number][];
    const xs = room.polygon.map((p) => p[0]), ys = room.polygon.map((p) => p[1]);
    const minx = Math.min(...xs), maxx = Math.max(...xs), miny = Math.min(...ys), maxy = Math.max(...ys);
    const step = 2.2, m = 0.7;
    const pts: [number, number, number][] = [];
    for (let x = minx + m; x <= maxx - m; x += step)
      for (let y = miny + m; y <= maxy - m; y += step)
        if (pointInPolygon(room.polygon, x, y)) pts.push([x, room.ceilingHeight - 0.02, -y]);
    return pts;
  }, [room.polygon, room.ceilingHeight]);
  // Real CC0 PBR floor: warm oak in guest areas, hard-wearing concrete in wet/back-of-house,
  // terrazzo on the terrace. ShapeGeometry UVs are in plan metres → repeat = 1 / tileMetres.
  const wet =
    room.category === "wc" ||
    room.category === "wc_disabled" ||
    room.category === "kitchen" ||
    room.category === "preparation" ||
    room.category === "storage";
  const floorName = outdoor ? "terrazzo" : wet ? "concrete" : "oak";
  const tile = outdoor ? 2.0 : wet ? 2.5 : 1.6;
  const rep = r2(1 / tile);
  const floor = pbr(floorName, rep, rep);
  const floorTint = outdoor ? "#ffffff" : wet ? "#d8d8d6" : "#ffffff";

  return (
    <group>
      <mesh geometry={geom} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, 0]} receiveShadow userData={{ floor: true }}>
        <meshStandardMaterial
          map={floor.map}
          normalMap={floor.normalMap}
          roughnessMap={floor.roughnessMap}
          color={floorTint}
          roughness={1}
          metalness={0}
          side={THREE.DoubleSide}
        />
      </mesh>
      {room.ceilingHeight > 0 && (
        // BackSide: seen from below (interior/walk views) but culled from above, so the
        // top-down / dollhouse view still sees straight into the furnished rooms.
        <mesh geometry={geom} rotation={[-Math.PI / 2, 0, 0]} position={[0, room.ceilingHeight, 0]}>
          <meshStandardMaterial color={pal.ceiling} roughness={0.95} metalness={0} side={THREE.BackSide} />
        </mesh>
      )}
      {downlights.map((p, i) => (
        <mesh key={`dl${i}`} position={p}>
          <cylinderGeometry args={[0.08, 0.08, 0.02, 16]} />
          <meshStandardMaterial color="#fff6e6" emissive={pal.light.pendant} emissiveIntensity={2.4} roughness={0.4} />
        </mesh>
      ))}
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
