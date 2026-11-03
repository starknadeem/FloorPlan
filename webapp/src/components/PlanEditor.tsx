"use client";

import { useMemo, useRef, useState, type CSSProperties } from "react";
import type {
  CafeScene,
  Fixture,
  Opening,
  Room,
  Vec2,
  Wall,
} from "@/types/cafescene";
import { wallLength, polygonCentroid } from "@/lib/geometry";
import { regularizeScene, scaleScene } from "@/lib/regularize";
import { FIXTURE_CATEGORIES, OPENING_TYPES, ROOM_CATEGORIES } from "@/lib/parser/types";

type Sel = { kind: "wall" | "fixture" | "room" | "opening"; id: string } | null;
type Drag = { kind: "wall"; id: string; part: "a" | "b" } | { kind: "fixture"; id: string; off: Vec2 } | null;

const MARGIN = 1.2; // meters of padding around the plan

function confColor(c: number): string {
  if (c >= 0.8) return "#2e7d32";
  if (c >= 0.6) return "#b9770e";
  return "#c0392b";
}

export default function PlanEditor({
  scene,
  onApply,
  onCancel,
}: {
  scene: CafeScene;
  onApply: (s: CafeScene) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<CafeScene>(() => structuredClone(scene));
  const [sel, setSel] = useState<Sel>(null);
  const [scaleInput, setScaleInput] = useState("");
  const svgRef = useRef<SVGSVGElement>(null);
  const drag = useRef<Drag>(null);

  const bounds = useMemo(() => {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    const c = (x: number, y: number) => {
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x); maxY = Math.max(maxY, y);
    };
    for (const w of draft.walls) { c(w.a[0], w.a[1]); c(w.b[0], w.b[1]); }
    for (const r of draft.rooms) for (const p of r.polygon) c(p[0], p[1]);
    for (const f of draft.fixtures) c(f.position[0], f.position[1]);
    if (!isFinite(minX)) { minX = 0; minY = 0; maxX = 10; maxY = 10; }
    return { minX, minY, maxX, maxY };
  }, [draft]);

  const [pxPerM, setPxPerM] = useState(() => {
    const w = bounds.maxX - bounds.minX + 2 * MARGIN;
    const h = bounds.maxY - bounds.minY + 2 * MARGIN;
    return Math.max(8, Math.min(980 / w, 660 / h));
  });

  const ox = bounds.minX - MARGIN;
  const oyTop = bounds.maxY + MARGIN;
  const svgW = (bounds.maxX - bounds.minX + 2 * MARGIN) * pxPerM;
  const svgH = (bounds.maxY - bounds.minY + 2 * MARGIN) * pxPerM;
  const sx = (x: number) => (x - ox) * pxPerM;
  const sy = (y: number) => (oyTop - y) * pxPerM;
  const toPlan = (clientX: number, clientY: number): Vec2 => {
    const r = svgRef.current!.getBoundingClientRect();
    return [(clientX - r.left) / pxPerM + ox, oyTop - (clientY - r.top) / pxPerM];
  };

  // ---- mutations -------------------------------------------------------------
  const patchWall = (id: string, p: Partial<Wall>) =>
    setDraft((d) => ({ ...d, walls: d.walls.map((w) => (w.id === id ? { ...w, ...p } : w)) }));
  const patchFixture = (id: string, p: Partial<Fixture>) =>
    setDraft((d) => ({ ...d, fixtures: d.fixtures.map((f) => (f.id === id ? { ...f, ...p } : f)) }));
  const patchRoom = (id: string, p: Partial<Room>) =>
    setDraft((d) => ({ ...d, rooms: d.rooms.map((r) => (r.id === id ? { ...r, ...p } : r)) }));
  const patchOpening = (id: string, p: Partial<Opening>) =>
    setDraft((d) => ({ ...d, openings: d.openings.map((o) => (o.id === id ? { ...o, ...p } : o)) }));

  function deleteSelected() {
    if (!sel) return;
    setDraft((d) => {
      if (sel.kind === "wall") return { ...d, walls: d.walls.filter((w) => w.id !== sel.id), openings: d.openings.filter((o) => o.wallId !== sel.id) };
      if (sel.kind === "fixture") return { ...d, fixtures: d.fixtures.filter((f) => f.id !== sel.id) };
      if (sel.kind === "room") return { ...d, rooms: d.rooms.filter((r) => r.id !== sel.id) };
      return { ...d, openings: d.openings.filter((o) => o.id !== sel.id) };
    });
    setSel(null);
  }

  function applyScaleFromWall() {
    if (!sel || sel.kind !== "wall") return;
    const w = draft.walls.find((x) => x.id === sel.id);
    const target = parseFloat(scaleInput);
    if (!w || !isFinite(target) || target <= 0) return;
    const cur = wallLength(w.a, w.b);
    if (cur <= 0) return;
    setDraft((d) => scaleScene(d, target / cur));
    setScaleInput("");
  }

  // ---- drag ------------------------------------------------------------------
  function onPointerMove(e: React.PointerEvent) {
    if (!drag.current) return;
    const [x, y] = toPlan(e.clientX, e.clientY);
    const dr = drag.current;
    if (dr.kind === "wall") patchWall(dr.id, { [dr.part]: [x, y] } as Partial<Wall>);
    else patchFixture(dr.id, { position: [x - dr.off[0], y - dr.off[1]] });
  }
  function endDrag() { drag.current = null; }

  // ---- render helpers --------------------------------------------------------
  const selected =
    sel?.kind === "wall" ? draft.walls.find((w) => w.id === sel.id)
    : sel?.kind === "fixture" ? draft.fixtures.find((f) => f.id === sel.id)
    : sel?.kind === "room" ? draft.rooms.find((r) => r.id === sel.id)
    : sel?.kind === "opening" ? draft.openings.find((o) => o.id === sel.id)
    : undefined;

  return (
    <div style={S.root}>
      {/* Toolbar */}
      <div style={S.toolbar}>
        <div style={{ fontWeight: 700, fontSize: 14 }}>Verify &amp; correct plan</div>
        <span style={S.dim}>·</span>
        <button style={S.tbtn} onClick={() => setPxPerM((p) => p * 0.85)}>−</button>
        <input type="range" min={6} max={80} step={1} value={pxPerM} onChange={(e) => setPxPerM(Number(e.target.value))} />
        <button style={S.tbtn} onClick={() => setPxPerM((p) => p * 1.18)}>+</button>
        <span style={S.dim}>zoom</span>
        <div style={{ flex: 1 }} />
        <button style={S.tbtn} onClick={() => setDraft((d) => regularizeScene(d, { tol: 0.3 }))} title="Snap near-axis walls & align shared coordinates">
          Regularize
        </button>
        <button style={{ ...S.tbtn, color: sel ? "#c0392b" : "#bbb" }} disabled={!sel} onClick={deleteSelected}>
          Delete
        </button>
        <button style={S.cancel} onClick={onCancel}>Cancel</button>
        <button style={S.apply} onClick={() => onApply(draft)}>Apply → 3D</button>
      </div>

      <div style={S.body}>
        {/* Canvas */}
        <div style={S.canvasWrap}>
          <svg
            ref={svgRef}
            width={svgW}
            height={svgH}
            style={{ display: "block", background: "#f6f3ec" }}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerLeave={endDrag}
            onPointerDown={(e) => { if (e.target === e.currentTarget) setSel(null); }}
          >
            {/* grid */}
            <defs>
              <pattern id="g" width={pxPerM} height={pxPerM} patternUnits="userSpaceOnUse">
                <path d={`M ${pxPerM} 0 L 0 0 0 ${pxPerM}`} fill="none" stroke="#e7e1d4" strokeWidth={1} />
              </pattern>
            </defs>
            <rect width={svgW} height={svgH} fill="url(#g)" onPointerDown={() => setSel(null)} />

            {/* rooms */}
            {draft.rooms.map((r) => {
              const pts = r.polygon.map((p) => `${sx(p[0])},${sy(p[1])}`).join(" ");
              const cen = polygonCentroid(r.polygon);
              const isSel = sel?.kind === "room" && sel.id === r.id;
              return (
                <g key={r.id} onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: "room", id: r.id }); }} style={{ cursor: "pointer" }}>
                  <polygon points={pts} fill={isSel ? "rgba(154,107,47,0.14)" : "rgba(154,107,47,0.05)"} stroke={isSel ? "#9a6b2f" : "#cbb89a"} strokeWidth={isSel ? 2 : 1} />
                  <text x={sx(cen[0])} y={sy(cen[1])} textAnchor="middle" fontSize={12} fill="#6b655c">{r.name}</text>
                </g>
              );
            })}

            {/* walls */}
            {draft.walls.map((w) => {
              const isSel = sel?.kind === "wall" && sel.id === w.id;
              return (
                <line
                  key={w.id}
                  x1={sx(w.a[0])} y1={sy(w.a[1])} x2={sx(w.b[0])} y2={sy(w.b[1])}
                  stroke={isSel ? "#1565c0" : confColor(w.confidence)}
                  strokeWidth={Math.max(4, w.thickness * pxPerM)}
                  strokeLinecap="round"
                  style={{ cursor: "pointer" }}
                  onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: "wall", id: w.id }); }}
                />
              );
            })}

            {/* openings */}
            {draft.openings.map((o) => {
              const w = draft.walls.find((x) => x.id === o.wallId);
              if (!w) return null;
              const L = wallLength(w.a, w.b) || 1;
              const t = (o.offset + o.width / 2) / L;
              const px = w.a[0] + (w.b[0] - w.a[0]) * t;
              const py = w.a[1] + (w.b[1] - w.a[1]) * t;
              const isSel = sel?.kind === "opening" && sel.id === o.id;
              return (
                <circle key={o.id} cx={sx(px)} cy={sy(py)} r={6}
                  fill={o.type === "window" ? "#4a90d9" : "#8a5a2b"} stroke={isSel ? "#111" : "#fff"} strokeWidth={2}
                  style={{ cursor: "pointer" }}
                  onPointerDown={(e) => { e.stopPropagation(); setSel({ kind: "opening", id: o.id }); }}
                />
              );
            })}

            {/* fixtures */}
            {draft.fixtures.map((f) => {
              const isSel = sel?.kind === "fixture" && sel.id === f.id;
              const fw = Math.max(5, f.footprint[0] * pxPerM);
              const fh = Math.max(5, f.footprint[1] * pxPerM);
              return (
                <g key={f.id} transform={`translate(${sx(f.position[0])},${sy(f.position[1])}) rotate(${-f.rotation})`}
                  style={{ cursor: "grab" }}
                  onPointerDown={(e) => {
                    e.stopPropagation();
                    setSel({ kind: "fixture", id: f.id });
                    const [mx, my] = toPlan(e.clientX, e.clientY);
                    drag.current = { kind: "fixture", id: f.id, off: [mx - f.position[0], my - f.position[1]] };
                  }}
                >
                  <rect x={-fw / 2} y={-fh / 2} width={fw} height={fh}
                    fill={isSel ? "rgba(21,101,192,0.25)" : "rgba(176,124,70,0.35)"}
                    stroke={isSel ? "#1565c0" : confColor(f.confidence)} strokeWidth={isSel ? 2 : 1.2} rx={2} />
                </g>
              );
            })}

            {/* wall endpoint handles (selected) */}
            {sel?.kind === "wall" && (() => {
              const w = draft.walls.find((x) => x.id === sel.id);
              if (!w) return null;
              return (["a", "b"] as const).map((part) => (
                <circle key={part} cx={sx(w[part][0])} cy={sy(w[part][1])} r={7} fill="#fff" stroke="#1565c0" strokeWidth={2.5}
                  style={{ cursor: "move" }}
                  onPointerDown={(e) => { e.stopPropagation(); drag.current = { kind: "wall", id: w.id, part }; }}
                />
              ));
            })()}
          </svg>
        </div>

        {/* Inspector */}
        <div style={S.panel}>
          <div style={S.legend}>
            <b>Confidence</b>
            <span><i style={{ ...S.dot, background: "#2e7d32" }} />high</span>
            <span><i style={{ ...S.dot, background: "#b9770e" }} />med</span>
            <span><i style={{ ...S.dot, background: "#c0392b" }} />low</span>
          </div>

          {!selected && <div style={S.hint}>Click a wall, fixture, room, or opening to edit it. Drag wall endpoints and fixtures to reposition. Low-confidence items (red) are the ones most worth checking.</div>}

          {selected && sel?.kind === "wall" && (
            <>
              <h3 style={S.h3}>Wall</h3>
              <Num label="Length (m)" value={wallLength((selected as Wall).a, (selected as Wall).b)} readOnly />
              <Num label="Thickness (m)" value={(selected as Wall).thickness} step={0.01} onChange={(v) => patchWall(sel.id, { thickness: v })} />
              <Num label="Height (m)" value={(selected as Wall).height} step={0.05} onChange={(v) => patchWall(sel.id, { height: v })} />
              <div style={S.scaleBox}>
                <div style={{ fontSize: 11, color: "#6b655c", marginBottom: 4 }}>Set this wall&apos;s true length to rescale the whole plan:</div>
                <div style={{ display: "flex", gap: 6 }}>
                  <input style={S.in} placeholder="e.g. 10.93" value={scaleInput} onChange={(e) => setScaleInput(e.target.value)} />
                  <button style={S.tbtn} onClick={applyScaleFromWall}>Rescale</button>
                </div>
              </div>
            </>
          )}

          {selected && sel?.kind === "fixture" && (
            <>
              <h3 style={S.h3}>Fixture</h3>
              <Txt label="Name" value={(selected as Fixture).name} onChange={(v) => patchFixture(sel.id, { name: v })} />
              <SelectInput label="Category" value={(selected as Fixture).category} options={FIXTURE_CATEGORIES as readonly string[]} onChange={(v) => patchFixture(sel.id, { category: v as Fixture["category"] })} />
              <Num label="Width (m)" value={(selected as Fixture).footprint[0]} step={0.05} onChange={(v) => patchFixture(sel.id, { footprint: [v, (selected as Fixture).footprint[1]] })} />
              <Num label="Depth (m)" value={(selected as Fixture).footprint[1]} step={0.05} onChange={(v) => patchFixture(sel.id, { footprint: [(selected as Fixture).footprint[0], v] })} />
              <Num label="Height (m)" value={(selected as Fixture).height ?? 0} step={0.05} onChange={(v) => patchFixture(sel.id, { height: v })} />
              <Num label="Rotation (°)" value={(selected as Fixture).rotation} step={5} onChange={(v) => patchFixture(sel.id, { rotation: v })} />
            </>
          )}

          {selected && sel?.kind === "room" && (
            <>
              <h3 style={S.h3}>Room</h3>
              <Txt label="Name" value={(selected as Room).name} onChange={(v) => patchRoom(sel.id, { name: v })} />
              <SelectInput label="Category" value={(selected as Room).category} options={ROOM_CATEGORIES as readonly string[]} onChange={(v) => patchRoom(sel.id, { category: v as Room["category"] })} />
              <Num label="Ceiling height (m)" value={(selected as Room).ceilingHeight} step={0.05} onChange={(v) => patchRoom(sel.id, { ceilingHeight: v })} />
            </>
          )}

          {selected && sel?.kind === "opening" && (
            <>
              <h3 style={S.h3}>Opening</h3>
              <SelectInput label="Type" value={(selected as Opening).type} options={OPENING_TYPES as readonly string[]} onChange={(v) => patchOpening(sel.id, { type: v as Opening["type"] })} />
              <Num label="Offset (m)" value={(selected as Opening).offset} step={0.05} onChange={(v) => patchOpening(sel.id, { offset: v })} />
              <Num label="Width (m)" value={(selected as Opening).width} step={0.05} onChange={(v) => patchOpening(sel.id, { width: v })} />
              <Num label="Height (m)" value={(selected as Opening).height} step={0.05} onChange={(v) => patchOpening(sel.id, { height: v })} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Num({ label, value, onChange, step = 0.1, readOnly }: { label: string; value: number; onChange?: (v: number) => void; step?: number; readOnly?: boolean }) {
  return (
    <label style={S.field}>
      <span style={S.flabel}>{label}</span>
      <input type="number" step={step} value={Number.isFinite(value) ? Number(value.toFixed(3)) : 0} readOnly={readOnly}
        onChange={(e) => { const n = parseFloat(e.target.value); if (Number.isFinite(n)) onChange?.(n); }} style={{ ...S.in, background: readOnly ? "#f0ece3" : "#fff" }} />
    </label>
  );
}
function Txt({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label style={S.field}><span style={S.flabel}>{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} style={S.in} /></label>
  );
}
function SelectInput({ label, value, options, onChange }: { label: string; value: string; options: readonly string[]; onChange: (v: string) => void }) {
  return (
    <label style={S.field}><span style={S.flabel}>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={S.in}>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select></label>
  );
}

const S: Record<string, CSSProperties> = {
  root: { position: "fixed", inset: 0, display: "flex", flexDirection: "column", background: "#efeadf", fontFamily: "system-ui, sans-serif" },
  toolbar: { display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "#fff", borderBottom: "1px solid #e2dccf", boxShadow: "0 1px 6px rgba(0,0,0,0.06)" },
  dim: { color: "#aaa", fontSize: 12 },
  tbtn: { border: "1px solid #d6cfbf", background: "#faf8f3", padding: "6px 12px", borderRadius: 7, fontSize: 13, cursor: "pointer", color: "#3a352e" },
  cancel: { border: "1px solid #d6cfbf", background: "transparent", padding: "7px 14px", borderRadius: 7, fontSize: 13, cursor: "pointer", color: "#4a453d" },
  apply: { border: "none", background: "#23201b", color: "#fff", padding: "7px 16px", borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: "pointer" },
  body: { flex: 1, display: "flex", minHeight: 0 },
  canvasWrap: { flex: 1, overflow: "auto", padding: 16 },
  panel: { width: 290, flex: "0 0 290px", borderLeft: "1px solid #e2dccf", background: "#fff", padding: 16, overflowY: "auto" },
  legend: { display: "flex", gap: 12, alignItems: "center", fontSize: 11, color: "#6b655c", marginBottom: 14 },
  dot: { display: "inline-block", width: 10, height: 10, borderRadius: 3, marginRight: 4, verticalAlign: "middle" },
  hint: { fontSize: 12.5, color: "#6b655c", lineHeight: 1.5 },
  h3: { fontSize: 13, letterSpacing: 1, textTransform: "uppercase", color: "#9a6b2f", margin: "4px 0 12px" },
  field: { display: "flex", flexDirection: "column", gap: 3, marginBottom: 10 },
  flabel: { fontSize: 11, color: "#8a847a" },
  in: { border: "1px solid #d6cfbf", borderRadius: 6, padding: "6px 8px", fontSize: 13, width: "100%", boxSizing: "border-box" },
  scaleBox: { marginTop: 10, padding: 10, background: "#faf7f0", borderRadius: 8, border: "1px solid #ece4d4" },
};
