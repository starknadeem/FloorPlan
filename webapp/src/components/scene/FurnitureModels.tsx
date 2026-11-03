"use client";

import type { ReactNode } from "react";
import * as THREE from "three";
import type { Fixture } from "@/types/cafescene";
import { fixtureHeight } from "@/lib/geometry";
import type { StylePalette } from "@/lib/design/palette";
import { woodTexture } from "@/lib/design/textures";

/* ---- primitive helpers ------------------------------------------------------
   All models are built with their base at y=0, centered on x/z, sized to the
   fixture footprint (w = x, d = z) and height (h = y). The parent group handles
   world position + rotation. */

type BoxP = {
  p: [number, number, number];
  s: [number, number, number];
  c: string;
  r?: number;
  m?: number;
  e?: string;
  ei?: number;
  transparent?: boolean;
  opacity?: number;
  tex?: THREE.Texture;
};
function Box({ p, s, c, r = 0.75, m = 0, e, ei = 0, transparent, opacity = 1, tex }: BoxP) {
  return (
    <mesh position={p} castShadow receiveShadow>
      <boxGeometry args={s} />
      <meshStandardMaterial
        map={tex}
        color={tex ? "#ffffff" : c}
        roughness={r}
        metalness={m}
        emissive={e ?? "#000000"}
        emissiveIntensity={ei}
        transparent={transparent}
        opacity={opacity}
      />
    </mesh>
  );
}

type CylP = {
  p: [number, number, number];
  rt: number;
  rb: number;
  h: number;
  c: string;
  r?: number;
  m?: number;
  seg?: number;
  e?: string;
  ei?: number;
  tex?: THREE.Texture;
};
function Cyl({ p, rt, rb, h, c, r = 0.6, m = 0, seg = 20, e, ei = 0, tex }: CylP) {
  return (
    <mesh position={p} castShadow receiveShadow>
      <cylinderGeometry args={[rt, rb, h, seg]} />
      <meshStandardMaterial map={tex} color={tex ? "#ffffff" : c} roughness={r} metalness={m} emissive={e ?? "#000000"} emissiveIntensity={ei} />
    </mesh>
  );
}

function legs(w: number, d: number, h: number, color: string, inset = 0.07, t = 0.05) {
  const xs = [-(w / 2 - inset), w / 2 - inset];
  const zs = [-(d / 2 - inset), d / 2 - inset];
  const out: ReactNode[] = [];
  let i = 0;
  for (const x of xs) for (const z of zs) out.push(<Box key={i++} p={[x, h / 2, z]} s={[t, h, t]} c={color} r={0.5} m={0.6} />);
  return out;
}

export default function FurnitureModel({ f, pal }: { f: Fixture; pal: StylePalette }) {
  const w = f.footprint[0];
  const d = f.footprint[1];
  const h = fixtureHeight(f);

  switch (f.category) {
    case "table": {
      const topT = 0.05;
      return (
        <group>
          {legs(w, d, h - topT, pal.metal)}
          <Box p={[0, h - topT / 2, 0]} s={[w, topT, d]} c={pal.wood} r={0.5} tex={woodTexture(pal.wood)} />
        </group>
      );
    }
    case "chair": {
      const seatH = Math.min(0.46, h * 0.5);
      return (
        <group>
          {legs(w, d, seatH, pal.metal, 0.05, 0.04)}
          <Box p={[0, seatH, 0]} s={[w, 0.06, d]} c={pal.fabric} r={0.9} />
          <Box p={[0, seatH + (h - seatH) / 2, -d / 2 + 0.04]} s={[w, h - seatH, 0.05]} c={pal.fabric} r={0.9} />
        </group>
      );
    }
    case "stool": {
      const seatH = h - 0.06;
      return (
        <group>
          {legs(w, d, seatH, pal.metal, 0.05, 0.035)}
          <Cyl p={[0, seatH, 0]} rt={Math.min(w, d) / 2} rb={Math.min(w, d) / 2} h={0.06} c={pal.woodDark} r={0.6} tex={woodTexture(pal.woodDark)} />
        </group>
      );
    }
    case "counter":
    case "cashier": {
      const topT = 0.05;
      return (
        <group>
          <Box p={[0, (h - topT) / 2, 0]} s={[w - 0.04, h - topT, d - 0.04]} c={pal.wood} r={0.6} tex={woodTexture(pal.wood)} />
          <Box p={[0, h - topT / 2, 0]} s={[w, topT, d]} c={pal.counterTop} r={0.4} m={0.1} />
          {f.category === "cashier" && <Box p={[0, h + 0.12, 0]} s={[w * 0.5, 0.24, 0.03]} c="#20242a" r={0.3} e="#101418" ei={0.3} />}
        </group>
      );
    }
    case "shelving": {
      const t = 0.04;
      return (
        <group>
          <Box p={[-w / 2 + t / 2, h / 2, 0]} s={[t, h, d]} c={pal.woodDark} r={0.6} tex={woodTexture(pal.woodDark)} />
          <Box p={[w / 2 - t / 2, h / 2, 0]} s={[t, h, d]} c={pal.woodDark} r={0.6} tex={woodTexture(pal.woodDark)} />
          {[0.1, h * 0.4, h * 0.7, h - 0.05].map((y, i) => (
            <Box key={i} p={[0, y, 0]} s={[w, t, d]} c={pal.wood} r={0.6} tex={woodTexture(pal.wood)} />
          ))}
        </group>
      );
    }
    case "espresso_machine": {
      return (
        <group>
          <Box p={[0, h * 0.42, 0]} s={[w, h * 0.84, d]} c={pal.stainless} r={0.3} m={0.8} />
          <Box p={[0, h * 0.9, 0]} s={[w * 0.9, h * 0.2, d * 0.85]} c="#2b2e31" r={0.4} m={0.5} />
          <Box p={[0, h * 0.5, d / 2]} s={[w * 0.7, 0.06, 0.04]} c="#17191b" r={0.4} />
          <Cyl p={[-w * 0.2, h * 0.38, d / 2 + 0.02]} rt={0.03} rb={0.03} h={0.1} c="#17191b" seg={10} />
          <Cyl p={[w * 0.2, h * 0.38, d / 2 + 0.02]} rt={0.03} rb={0.03} h={0.1} c="#17191b" seg={10} />
        </group>
      );
    }
    case "grinder": {
      return (
        <group>
          <Box p={[0, h * 0.35, 0]} s={[w, h * 0.7, d]} c={pal.stainless} r={0.35} m={0.7} />
          <Cyl p={[0, h * 0.82, 0]} rt={w * 0.42} rb={w * 0.3} h={h * 0.3} c="#2b2e31" r={0.3} seg={16} />
        </group>
      );
    }
    case "blender":
    case "mixer":
    case "boiler": {
      return (
        <group>
          <Box p={[0, h * 0.4, 0]} s={[w, h * 0.8, d]} c={pal.stainless} r={0.35} m={0.7} />
          <Cyl p={[0, h * 0.9, 0]} rt={w * 0.3} rb={w * 0.3} h={h * 0.25} c="#30343a" r={0.3} seg={14} />
        </group>
      );
    }
    case "fridge":
    case "freezer": {
      return (
        <group>
          <Box p={[0, h / 2, 0]} s={[w, h, d]} c={pal.stainless} r={0.3} m={0.75} />
          <Box p={[w / 2 - 0.06, h * 0.55, d / 2]} s={[0.04, h * 0.5, 0.04]} c="#1d2023" r={0.3} m={0.6} />
          <Box p={[0, h * 0.5, d / 2 + 0.001]} s={[w * 0.98, 0.012, 0.01]} c="#8c9196" r={0.4} />
        </group>
      );
    }
    case "oven": {
      return (
        <group>
          <Box p={[0, h / 2, 0]} s={[w, h, d]} c="#3a3d40" r={0.4} m={0.5} />
          <Box p={[0, h * 0.45, d / 2]} s={[w * 0.82, h * 0.5, 0.03]} c="#17191b" r={0.2} m={0.3} e="#0a0c0e" ei={0.2} />
          <Box p={[0, h * 0.75, d / 2 + 0.02]} s={[w * 0.7, 0.04, 0.04]} c={pal.stainless} r={0.3} m={0.8} />
        </group>
      );
    }
    case "dishwasher":
    case "ice_maker": {
      return (
        <group>
          <Box p={[0, h / 2, 0]} s={[w, h, d]} c={pal.stainless} r={0.35} m={0.7} />
          <Box p={[0, h * 0.85, d / 2 + 0.001]} s={[w * 0.6, 0.03, 0.01]} c="#1d2023" r={0.4} />
        </group>
      );
    }
    case "cooling_case":
    case "display_case": {
      const baseH = h * 0.5;
      return (
        <group>
          <Box p={[0, baseH / 2, 0]} s={[w, baseH, d]} c={pal.woodDark} r={0.6} />
          <Box p={[0, baseH + 0.02, 0]} s={[w, 0.04, d]} c={pal.counterTop} r={0.4} />
          <Box p={[0, baseH + (h - baseH) / 2, 0]} s={[w * 0.98, h - baseH, d * 0.98]} c={pal.glass} r={0.1} m={0.1} transparent opacity={0.28} />
        </group>
      );
    }
    case "sink": {
      return (
        <group>
          <Box p={[0, h / 2, 0]} s={[w, h, d]} c={pal.stainless} r={0.4} m={0.7} />
          <Box p={[0, h - 0.03, 0]} s={[w * 0.7, 0.06, d * 0.6]} c="#6f7479" r={0.5} m={0.5} />
        </group>
      );
    }
    case "monitor":
    case "menu_board":
    case "signage": {
      const dark = f.category === "monitor";
      return (
        <Box
          p={[0, h / 2, 0]}
          s={[Math.max(w, 0.1), h, Math.max(d, 0.04)]}
          c={dark ? "#15181b" : pal.woodDark}
          r={0.4}
          e={dark ? "#223042" : pal.accent}
          ei={dark ? 0.35 : 0.12}
        />
      );
    }
    case "sofa":
    case "banquette": {
      const seatH = h * 0.5;
      return (
        <group>
          <Box p={[0, seatH / 2, 0]} s={[w, seatH, d]} c={pal.fabric} r={0.9} />
          <Box p={[0, seatH, 0.02]} s={[w, 0.12, d * 0.9]} c={pal.fabric} r={0.95} />
          <Box p={[0, seatH + (h - seatH) / 2, -d / 2 + 0.08]} s={[w, h - seatH, 0.16]} c={pal.fabric} r={0.9} />
        </group>
      );
    }
    case "plant": {
      const potH = Math.min(0.35, h * 0.35);
      return (
        <group>
          <Cyl p={[0, potH / 2, 0]} rt={Math.min(w, d) * 0.4} rb={Math.min(w, d) * 0.32} h={potH} c={pal.plantPot} r={0.7} />
          <Cyl p={[0, potH + (h - potH) * 0.45, 0]} rt={0.02} rb={0.03} h={(h - potH) * 0.9} c="#5a4632" seg={8} />
          <mesh position={[0, potH + (h - potH) * 0.7, 0]} castShadow>
            <sphereGeometry args={[Math.max(w, d) * 0.5, 14, 12]} />
            <meshStandardMaterial color={pal.foliage} roughness={0.9} />
          </mesh>
        </group>
      );
    }
    case "pendant_light": {
      // group origin sits at mount height; shade near top, bulb below
      return (
        <group>
          <Cyl p={[0, h, 0]} rt={0.01} rb={0.01} h={0.25} c="#2a2d30" seg={6} />
          <mesh position={[0, h * 0.5, 0]} castShadow>
            <coneGeometry args={[Math.max(w, 0.16) * 0.6, h * 0.6, 18, 1, true]} />
            <meshStandardMaterial color="#2a2d30" roughness={0.5} metalness={0.4} side={THREE.DoubleSide} />
          </mesh>
          <mesh position={[0, h * 0.28, 0]}>
            <sphereGeometry args={[0.05, 10, 10]} />
            <meshStandardMaterial color={pal.light.pendant} emissive={pal.light.pendant} emissiveIntensity={2.2} />
          </mesh>
        </group>
      );
    }
    case "umbrella": {
      return (
        <group>
          <Cyl p={[0, h * 0.5, 0]} rt={0.03} rb={0.03} h={h} c={pal.metal} seg={10} />
          <mesh position={[0, h, 0]} castShadow>
            <coneGeometry args={[Math.max(w, d) * 0.5, h * 0.25, 10]} />
            <meshStandardMaterial color={pal.accent} roughness={0.8} />
          </mesh>
        </group>
      );
    }
    default:
      return <Box p={[0, h / 2, 0]} s={[w, h, d]} c="#b7b2a8" r={0.8} />;
  }
}
