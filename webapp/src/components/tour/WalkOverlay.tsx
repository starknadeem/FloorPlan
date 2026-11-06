"use client";

// DOM chrome for the walkable tour: ident card + "where you are", mini-map, story/detail card,
// numbered stops, play/evening/map/controls actions, touch joystick, toasts and the help sheet.

import { useEffect, useRef, useSyncExternalStore, type CSSProperties, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import type { TourStore } from "@/lib/tour/store";
import type { RoomCategory } from "@/types/cafescene";

export function useTourVersion(store: TourStore) {
  return useSyncExternalStore(store.subscribe, () => store.version, () => store.version);
}

const C = {
  panel: "rgba(246,240,231,0.9)",
  ink: "#2f2119",
  muted: "#6e5a4a",
  accent: "#9a6a3a",
  line: "rgba(47,33,25,0.16)",
  chip: "#fffaf3",
  chipOn: "#3a271b",
  chipOnInk: "#f4eadb",
  shadow: "0 6px 24px rgba(28,18,12,0.22)",
  map: { floor: "#efe6d6", wet: "#e3dac8", terrace: "#b9aa98", solid: "#8d7f71", furn: "#5b3d2a", me: "#b5762f" },
};

const WET: RoomCategory[] = ["wc", "wc_disabled", "kitchen", "preparation", "storage"];

function drawMap(g: CanvasRenderingContext2D, store: TourStore, k: number, w: number, h: number) {
  const { bounds: B, map, stops } = store.model;
  const mx = (x: number) => (x - B.minX) * k;
  const mz = (z: number) => (z - B.minZ) * k;
  g.clearRect(0, 0, w, h);
  for (const r of map.rooms) {
    g.fillStyle = r.category === "seating_outdoor" ? C.map.terrace : WET.includes(r.category) ? C.map.wet : C.map.floor;
    g.beginPath();
    r.pts.forEach((p, i) => (i ? g.lineTo(mx(p[0]), mz(p[1])) : g.moveTo(mx(p[0]), mz(p[1]))));
    g.closePath();
    g.fill();
  }
  g.strokeStyle = C.map.solid;
  g.lineCap = "butt";
  for (const wl of map.walls) {
    g.lineWidth = Math.max(1.5, wl.t * k);
    g.beginPath();
    g.moveTo(mx(wl.a[0]), mz(wl.a[1]));
    g.lineTo(mx(wl.b[0]), mz(wl.b[1]));
    g.stroke();
  }
  g.fillStyle = C.map.furn;
  for (const r of map.rects) {
    g.save();
    g.translate(mx(r.x), mz(r.z));
    g.rotate(r.rot);
    g.fillRect((-r.w / 2) * k, (-r.d / 2) * k, Math.max(1, r.w * k), Math.max(1, r.d * k));
    g.restore();
  }
  const u = k / 6; // ui scale relative to the reference's 6 px/m
  stops.forEach((n, i) => {
    const x = mx(n.pos[0]), y = mz(n.pos[1]);
    g.beginPath();
    g.arc(x, y, 5.5 * u, 0, Math.PI * 2);
    g.fillStyle = i === store.currentNode ? C.accent : C.ink;
    g.fill();
    g.fillStyle = "#fff";
    g.font = `600 ${Math.round(7.5 * u)}px system-ui, sans-serif`;
    g.textAlign = "center";
    g.textBaseline = "middle";
    g.fillText(String(i + 1), x, y + 0.5);
  });
  const px = mx(store.cam.x), pz = mz(store.cam.z);
  const fov = ((store.fov * Math.PI) / 180) * 0.5 * 1.4;
  const len = 26 * u;
  const dir = Math.atan2(-Math.cos(store.cam.yaw), -Math.sin(store.cam.yaw));
  g.beginPath();
  g.moveTo(px, pz);
  g.arc(px, pz, len, dir - fov, dir + fov);
  g.closePath();
  g.fillStyle = C.map.me;
  g.globalAlpha = 0.3;
  g.fill();
  g.globalAlpha = 1;
  g.beginPath();
  g.arc(px, pz, 4.5 * u, 0, Math.PI * 2);
  g.fill();
  g.lineWidth = 2 * u;
  g.strokeStyle = "#fff";
  g.stroke();
}

function MiniMap({ store }: { store: TourStore }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const B = store.model.bounds;
  const MW = B.maxX - B.minX, MH = B.maxZ - B.minZ;
  const k = Math.min(200 / MW, 230 / MH);
  const W = Math.max(60, MW * k), H = Math.max(60, MH * k);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const g = c.getContext("2d");
    if (!g) return;
    const dpr = window.devicePixelRatio || 1;
    c.width = Math.round(W * dpr);
    c.height = Math.round(H * dpr);
    let raf = 0;
    const draw = () => {
      drawMap(g, store, k * dpr, c.width, c.height);
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [store, k, W, H]);

  const onClick = (e: RPointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    store.walkTo((e.clientX - r.left) / k + B.minX, (e.clientY - r.top) / k + B.minZ);
  };

  return (
    <div style={S.mapwrap}>
      <canvas ref={ref} style={{ width: W, height: H, display: "block", cursor: "crosshair" }} onClick={onClick} aria-label="Floor plan map. Click a spot to go there." />
      <div style={S.maphint}>Click to go there</div>
    </div>
  );
}

function Joystick({ store }: { store: TourStore }) {
  const knob = useRef<HTMLDivElement>(null);
  const id = useRef<number | null>(null);
  const move = (e: RPointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    let x = (e.clientX - (r.left + r.width / 2)) / (r.width / 2);
    let y = (e.clientY - (r.top + r.height / 2)) / (r.height / 2);
    const l = Math.hypot(x, y);
    if (l > 1) {
      x /= l;
      y /= l;
    }
    store.setJoy(Math.abs(x) < 0.12 ? 0 : x, Math.abs(y) < 0.12 ? 0 : y);
    if (knob.current) knob.current.style.transform = `translate(${x * 35}px,${y * 35}px)`;
  };
  const end = (e: RPointerEvent<HTMLDivElement>) => {
    if (e.pointerId !== id.current) return;
    id.current = null;
    store.setJoy(0, 0);
    if (knob.current) knob.current.style.transform = "";
  };
  return (
    <div
      style={S.joy}
      onPointerDown={(e) => {
        id.current = e.pointerId;
        e.currentTarget.setPointerCapture(e.pointerId);
        move(e);
      }}
      onPointerMove={(e) => {
        if (e.pointerId === id.current) move(e);
      }}
      onPointerUp={end}
      onPointerCancel={end}
    >
      <div ref={knob} style={S.knob} />
    </div>
  );
}

export default function WalkOverlay({
  store,
  projectName,
  subtitle,
  onExit,
  extraActions,
}: {
  store: TourStore;
  projectName: string;
  subtitle?: string;
  onExit?: () => void;
  extraActions?: (buttonStyle: CSSProperties) => ReactNode;
}) {
  useTourVersion(store);
  const coarse = typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;
  const toastOn = store.toastVisible;
  const stops = store.stops;

  return (
    <div style={S.root}>
      <div style={S.top}>
        <div style={S.ident}>
          <div style={S.wordmark}>{projectName}</div>
          {subtitle && <div style={S.site}>{subtitle}</div>}
          <div style={S.where}>
            {store.where.prefix} <b style={{ fontWeight: 600 }}>{store.where.name}</b>
          </div>
        </div>
        {store.mapVisible && <MiniMap store={store} />}
      </div>

      <div style={S.bottom}>
        {store.card && (
          <section style={S.story} aria-live="polite">
            <button style={S.close} onClick={() => store.hideCard()}>
              Close
            </button>
            <div style={S.kicker}>{store.card.kicker}</div>
            <h2 style={S.h2}>{store.card.title}</h2>
            <p style={S.p}>{store.card.text}</p>
          </section>
        )}
        <div style={S.bar}>
          <nav style={S.stops} aria-label="Tour stops">
            {stops.map((s, i) => {
              const on = i === store.currentNode;
              return (
                <button key={s.id} style={{ ...S.stop, ...(on ? S.stopOn : null) }} onClick={() => store.goNode(i)} aria-current={on ? "true" : undefined}>
                  <span style={{ ...S.n, ...(on ? S.nOn : null) }}>{i + 1}</span>
                  {s.name}
                </button>
              );
            })}
          </nav>
          <div style={S.actions}>
            <button style={{ ...S.act, ...S.primary }} onClick={() => store.toggleTour()}>
              {store.tourOn ? "Pause tour" : "Play tour"}
            </button>
            <button style={S.act} onClick={() => store.setEvening(!store.evening)}>
              {store.evening ? "Daytime" : "Evening"}
            </button>
            <button style={S.act} onClick={() => store.toggleMap()}>
              {store.mapVisible ? "Hide map" : "Show map"}
            </button>
            {extraActions?.(S.act)}
            <button style={S.act} onClick={() => store.setHelp(true)}>
              Controls
            </button>
            {onExit && (
              <button style={S.act} onClick={onExit} title="Back to the orbit / editing view">
                Exit
              </button>
            )}
          </div>
        </div>
      </div>

      {coarse && <Joystick store={store} />}

      <div style={{ ...S.toast, opacity: toastOn ? 1 : 0 }}>{store.toastText}</div>

      {store.help && (
        <div style={S.help}>
          <div style={S.helpPanel}>
            <h2 style={{ ...S.h2, fontSize: 22, margin: "0 0 6px" }}>Walk the café</h2>
            <p style={{ ...S.p, color: C.muted, marginBottom: 12 }}>
              A walkable model of {projectName}, built from the floor plan with the furnishing pass applied.
            </p>
            <ul style={S.helpList}>
              {coarse ? (
                <>
                  <li style={S.li}><b>Look around:</b> drag anywhere on the view.</li>
                  <li style={S.li}><b>Walk:</b> use the round stick, or tap the floor to walk there.</li>
                  <li style={S.li}><b>Details:</b> tap a bronze + marker.</li>
                  <li style={S.li}><b>Jump:</b> tap a numbered stop below.</li>
                </>
              ) : (
                <>
                  <li style={S.li}><b>Look around:</b> drag with the mouse.</li>
                  <li style={S.li}><b>Walk:</b> W A S D or arrow keys, hold Shift to go faster, or click the floor.</li>
                  <li style={S.li}><b>Details:</b> click a bronze + marker.</li>
                  <li style={S.li}><b>Jump:</b> pick a numbered stop or click the map.</li>
                </>
              )}
            </ul>
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 14 }}>
              <button style={S.act} onClick={() => store.setHelp(false)}>
                Explore freely
              </button>
              <button style={{ ...S.act, ...S.primary }} onClick={() => store.startTour()} disabled={!stops.length}>
                Play tour
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const panel: CSSProperties = {
  background: C.panel,
  backdropFilter: "blur(10px)",
  WebkitBackdropFilter: "blur(10px)",
  borderRadius: 14,
  boxShadow: C.shadow,
  pointerEvents: "auto",
  color: C.ink,
};

const S: Record<string, CSSProperties> = {
  root: { position: "absolute", inset: 0, pointerEvents: "none", fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif", color: C.ink },
  top: { position: "absolute", top: 12, left: 12, right: 12, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 },
  ident: { ...panel, padding: "10px 16px 11px", maxWidth: "min(360px, 62vw)" },
  wordmark: { fontWeight: 600, fontSize: 21, letterSpacing: "-0.01em", lineHeight: 1 },
  site: { fontSize: 13, color: C.muted, marginTop: 4 },
  where: { fontSize: 15, marginTop: 8, paddingTop: 8, borderTop: `1px solid ${C.line}` },
  mapwrap: { ...panel, padding: 8 },
  maphint: { fontSize: 11, color: C.muted, textAlign: "center", marginTop: 4 },
  bottom: { position: "absolute", left: 12, right: 12, bottom: 12, display: "flex", flexDirection: "column", gap: 10, alignItems: "flex-start" },
  story: { ...panel, maxWidth: 420, padding: "14px 16px 15px", position: "relative" },
  close: { position: "absolute", top: 8, right: 8, borderWidth: 0, background: "transparent", fontSize: 13, color: C.muted, padding: "6px 8px", borderRadius: 8, cursor: "pointer" },
  kicker: { fontSize: 13, color: C.accent, fontWeight: 500 },
  h2: { fontSize: 19, fontWeight: 500, margin: "2px 0 6px", letterSpacing: "-0.005em" },
  p: { fontSize: 14.5, lineHeight: 1.5, margin: 0 },
  bar: { ...panel, display: "flex", alignItems: "center", gap: 8, padding: 8, alignSelf: "stretch" },
  stops: { display: "flex", gap: 6, overflowX: "auto", scrollbarWidth: "none", flex: 1, minWidth: 0, padding: 2 },
  stop: { flex: "0 0 auto", display: "flex", alignItems: "center", gap: 7, borderWidth: 1, borderStyle: "solid", borderColor: C.line, background: C.chip, color: C.ink, borderRadius: 999, padding: "6px 12px 6px 6px", fontSize: 13.5, cursor: "pointer", whiteSpace: "nowrap" },
  stopOn: { background: C.chipOn, color: C.chipOnInk, borderColor: "transparent" },
  n: { width: 22, height: 22, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 600, background: C.line },
  nOn: { background: "rgba(255,255,255,0.18)" },
  actions: { display: "flex", gap: 6, flex: "0 0 auto" },
  act: { borderWidth: 1, borderStyle: "solid", borderColor: C.line, borderRadius: 999, padding: "8px 14px", fontSize: 13.5, cursor: "pointer", background: C.chip, color: C.ink, whiteSpace: "nowrap" },
  primary: { background: C.accent, color: "#fff", borderColor: "transparent", fontWeight: 500 },
  joy: { position: "absolute", left: 24, bottom: 150, width: 116, height: 116, borderRadius: "50%", background: C.panel, boxShadow: C.shadow, touchAction: "none", pointerEvents: "auto" },
  knob: { position: "absolute", left: "50%", top: "50%", width: 46, height: 46, margin: "-23px 0 0 -23px", borderRadius: "50%", background: C.accent, opacity: 0.9 },
  toast: { position: "absolute", left: "50%", top: "50%", transform: "translate(-50%,-50%)", background: C.panel, padding: "8px 14px", borderRadius: 999, fontSize: 13.5, boxShadow: C.shadow, transition: "opacity .2s", color: C.ink },
  help: { position: "absolute", inset: 0, display: "grid", placeItems: "center", background: "rgba(20,14,10,0.35)", padding: 20, pointerEvents: "auto" },
  helpPanel: { ...panel, padding: "20px 22px", maxWidth: 420, width: "100%" },
  helpList: { listStyle: "none", padding: 0, margin: 0 },
  li: { fontSize: 14, padding: "8px 0", borderTop: `1px solid ${C.line}`, lineHeight: 1.45 },
};
