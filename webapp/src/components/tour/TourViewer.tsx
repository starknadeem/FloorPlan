"use client";

// Photoreal 360 tour viewer. Shows Blender-rendered equirectangular panoramas on the inside of
// a sphere; drag to look around, scroll to zoom, click a room to teleport. This is the
// walkable + photoreal result that replaces the flat real-time box view.

import { Suspense, useRef, useState, type CSSProperties } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { useTexture, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";

interface LookRef {
  yaw: number;
  pitch: number;
}

export interface TourStop {
  id: string;
  name: string;
  category: string;
  position: [number, number];
  yawDeg: number;
  image: string; // absolute or app-relative URL to the equirectangular JPG
}

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

// The world (pano sphere) rotates instead of the camera — mutating our own group ref is allowed,
// whereas mutating the useThree camera is blocked by the react-hooks/immutability lint rule.
function PanoWorld({ url, lookRef }: { url: string; lookRef: React.RefObject<LookRef> }) {
  const tex = useTexture(url, (t) => {
    const tt = t as THREE.Texture;
    tt.colorSpace = THREE.SRGBColorSpace;
    tt.anisotropy = 8;
  });
  const group = useRef<THREE.Group>(null);

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    g.rotation.order = "YXZ";
    g.rotation.y = -lookRef.current.yaw;
    g.rotation.x = -lookRef.current.pitch;
  });

  return (
    <group ref={group}>
      {/* BackSide: we sit inside the sphere. scale.x = -1 un-mirrors the equirect image. */}
      <mesh scale={[-1, 1, 1]}>
        <sphereGeometry args={[20, 64, 40]} />
        <meshBasicMaterial map={tex} side={THREE.BackSide} toneMapped={false} />
      </mesh>
    </group>
  );
}

export default function TourViewer({
  stops,
  baseUrl,
  projectName,
  onExit,
}: {
  stops: TourStop[];
  baseUrl: string; // directory URL the stop.image names are relative to
  projectName?: string;
  onExit?: () => void;
}) {
  const [active, setActive] = useState(0);
  const [fade, setFade] = useState(false);
  const [fov, setFov] = useState(74);
  const look = useRef<LookRef>({ yaw: 0, pitch: 0 });
  const drag = useRef({ on: false, px: 0, py: 0 });
  const stop = stops[active];
  const url = stop.image.startsWith("http") || stop.image.startsWith("/")
    ? stop.image
    : `${baseUrl.replace(/\/$/, "")}/${stop.image}`;

  function go(i: number) {
    if (i === active) return;
    setFade(true);
    setTimeout(() => {
      look.current.yaw = 0;
      look.current.pitch = 0;
      setActive(i);
      setTimeout(() => setFade(false), 60);
    }, 180);
  }

  const onDown = (e: React.PointerEvent) => {
    drag.current = { on: true, px: e.clientX, py: e.clientY };
  };
  const onUp = () => (drag.current.on = false);
  const onMove = (e: React.PointerEvent) => {
    if (!drag.current.on) return;
    const dx = e.clientX - drag.current.px;
    const dy = e.clientY - drag.current.py;
    drag.current.px = e.clientX;
    drag.current.py = e.clientY;
    look.current.yaw -= dx * 0.0026;
    look.current.pitch = clamp(look.current.pitch - dy * 0.0026, -1.45, 1.45);
  };
  const onWheel = (e: React.WheelEvent) => {
    setFov((f) => clamp(f + e.deltaY * 0.03, 32, 92));
  };

  return (
    <div
      style={styles.wrap}
      onPointerDown={onDown}
      onPointerUp={onUp}
      onPointerLeave={onUp}
      onPointerMove={onMove}
      onWheel={onWheel}
    >
      <Canvas dpr={[1, 2]}>
        <PerspectiveCamera makeDefault position={[0, 0, 0]} fov={fov} near={0.1} far={100} />
        <Suspense fallback={null}>
          <PanoWorld key={url} url={url} lookRef={look} />
        </Suspense>
      </Canvas>

      <div style={{ ...styles.fade, opacity: fade ? 1 : 0 }} />

      {/* top bar */}
      <div style={styles.topBar}>
        <span style={styles.badge}>🎬 Photoreal Tour{projectName ? ` · ${projectName}` : ""}</span>
        <span style={styles.here}>{stop.name}</span>
        {onExit && (
          <button style={styles.exitBtn} onClick={onExit}>
            ✕ Exit tour
          </button>
        )}
      </div>

      {/* room / stop navigation strip */}
      <div style={styles.nav}>
        {stops.map((st, i) => (
          <button
            key={st.id}
            style={{ ...styles.navBtn, ...(i === active ? styles.navBtnActive : null) }}
            onClick={() => go(i)}
            title={st.name}
          >
            {st.name}
          </button>
        ))}
      </div>

      <div style={styles.hint}>Drag to look around · scroll to zoom · pick a room below to move</div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: { position: "absolute", inset: 0, background: "#0d0b09", overflow: "hidden" },
  fade: { position: "absolute", inset: 0, background: "#0d0b09", pointerEvents: "none", transition: "opacity 0.18s ease" },
  topBar: { position: "absolute", top: 14, left: 14, right: 14, display: "flex", alignItems: "center", gap: 12, pointerEvents: "none" },
  badge: { background: "rgba(20,17,14,0.72)", color: "#ffd9a0", border: "1px solid rgba(255,210,150,0.25)", padding: "6px 12px", borderRadius: 999, fontSize: 13, fontWeight: 700, backdropFilter: "blur(8px)" },
  here: { background: "rgba(20,17,14,0.72)", color: "#f3ece0", padding: "6px 12px", borderRadius: 999, fontSize: 13, backdropFilter: "blur(8px)" },
  exitBtn: { marginLeft: "auto", pointerEvents: "auto", background: "rgba(20,17,14,0.72)", color: "#f3ece0", border: "1px solid rgba(255,255,255,0.18)", padding: "6px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer", backdropFilter: "blur(8px)" },
  nav: { position: "absolute", bottom: 46, left: "50%", transform: "translateX(-50%)", display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 8, maxWidth: "90vw", padding: 8, background: "rgba(20,17,14,0.7)", borderRadius: 12, backdropFilter: "blur(8px)" },
  navBtn: { border: "1px solid rgba(255,255,255,0.16)", background: "rgba(255,255,255,0.06)", color: "#e8e0d2", padding: "7px 13px", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600, textTransform: "capitalize" },
  navBtnActive: { background: "#ffce8f", color: "#2a1d0c", borderColor: "#ffce8f" },
  hint: { position: "absolute", bottom: 14, left: "50%", transform: "translateX(-50%)", color: "rgba(255,255,255,0.6)", fontSize: 12 },
};
