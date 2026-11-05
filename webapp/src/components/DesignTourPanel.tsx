"use client";

// "AI design tour": the claude.ai flow inside the app. Floor plan page(s) + interior references
// (+ optional AI concept images) + a brief go to Claude, which designs the café and writes a
// complete walkable three.js tour. Streams progress, then opens the result.

import { useEffect, useRef, useState, type CSSProperties } from "react";
import type { CafeScene } from "@/types/cafescene";
import { DIRECTIONS } from "@/lib/design-blender/directions";

export interface ImageIn {
  data: string; // base64 (no prefix)
  mediaType: "image/jpeg" | "image/png" | "image/webp" | "image/gif";
  name?: string;
}

export interface BlenderResult {
  id: string;
  designUrl: string;
  stills: { url: string; label: string }[];
  tour?: { baseUrl: string; stops: TourStopLike[] };
  glbUrl?: string;
  sceneUrl?: string;
  live?: string;
}
export interface TourStopLike {
  id: string;
  name: string;
  category: string;
  position: [number, number];
  yawDeg: number;
  image: string;
}
export type OutputKind = "blender" | "blender-live" | "web";

export interface DesignMeta {
  id: string;
  projectName: string;
  brief: string;
  createdAt: string;
  model: string;
  chars: number;
  url: string;
  complete: boolean;
  usage?: { input_tokens: number; output_tokens: number };
}

export async function fileToImageIn(file: File): Promise<ImageIn | null> {
  const mt = file.type as ImageIn["mediaType"];
  if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(mt)) return null;
  const buf = await file.arrayBuffer();
  let bin = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return { data: btoa(bin), mediaType: mt, name: file.name };
}

const DEFAULT_BRIEF = ""; // empty on purpose: a pre-filled style made every design look the same

export default function DesignTourPanel({
  scene,
  planImages,
  onClose,
  onOpen,
  onBlenderResult,
}: {
  scene: CafeScene;
  planImages: ImageIn[];
  onClose: () => void;
  onOpen: (url: string) => void;
  onBlenderResult: (r: BlenderResult) => void;
}) {
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const [direction, setDirection] = useState(""); // "" = surprise me: the server picks a direction not used recently
  const [output, setOutput] = useState<OutputKind>("blender");
  const [renderMode, setRenderMode] = useState<"glb" | "stills" | "both">("glb");
  const [percent, setPercent] = useState<number | undefined>(undefined);
  const [blenderDesigns, setBlenderDesigns] = useState<(BlenderResult & { projectName: string; createdAt: string; complete: boolean })[]>([]);
  const [refs, setRefs] = useState<ImageIn[]>([]);
  const [plans, setPlans] = useState<ImageIn[]>(planImages);
  const [concepts, setConcepts] = useState<(ImageIn & { url: string; label: string })[]>([]);
  const [conceptMsg, setConceptMsg] = useState<string | null>(null);
  const [conceptBusy, setConceptBusy] = useState(false);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState<{ chars: number; label: string; elapsedMs: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [designs, setDesigns] = useState<DesignMeta[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const refInput = useRef<HTMLInputElement>(null);
  const planInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetch("/api/design-tour")
      .then((r) => r.json())
      .then((d) => setDesigns((d?.designs ?? []) as DesignMeta[]))
      .catch(() => {});
    fetch("/api/design-blender")
      .then((r) => r.json())
      .then((d) => setBlenderDesigns((d?.designs ?? []) as typeof blenderDesigns))
      .catch(() => {});
  }, []);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function addFiles(files: FileList | null, into: "refs" | "plans") {
    if (!files) return;
    const list: ImageIn[] = [];
    for (const f of Array.from(files)) {
      const img = await fileToImageIn(f);
      if (img) list.push(img);
    }
    if (into === "refs") setRefs((r) => [...r, ...list].slice(0, 8));
    else setPlans((p) => [...p, ...list].slice(0, 4));
  }

  /** Step 1: Gemini paints concept views from the plan + references + brief. Returns true on success. */
  async function generateConcepts(): Promise<boolean> {
    setConceptBusy(true);
    setConceptMsg(null);
    try {
      const res = await fetch("/api/concepts", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ projectName: scene.project.name, brief, count: 3, planImages: plans, references: refs, scene }),
      });
      const d = (await res.json()) as { error?: string; errors?: string[]; images?: { url: string; label: string; data: string; mediaType: string }[] };
      if (!res.ok) {
        setConceptMsg(d?.error || "Concept generation failed.");
        return false;
      }
      const imgs = (d.images ?? []).map((im) => ({ url: im.url, label: im.label, data: im.data, mediaType: (im.mediaType as ImageIn["mediaType"]) || "image/png", name: im.label }));
      setConcepts(imgs);
      if (d.errors?.length) setConceptMsg(d.errors.join(" · "));
      return imgs.length > 0;
    } catch (e) {
      setConceptMsg(e instanceof Error ? e.message : "Concept generation failed.");
      return false;
    } finally {
      setConceptBusy(false);
    }
  }

  /** Full flow: concept images, then the 3D design tour built from them. */
  async function runAll() {
    const ok = await generateConcepts();
    if (ok) await generate();
  }

  /** Blender flow: Claude writes design.py → Blender builds (live) or renders (headless). */
  async function generateBlender() {
    setBusy(true);
    setError(null);
    setPercent(2);
    setProgress({ chars: 0, label: "Sending the plan to the designer…", elapsedMs: 0 });
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const res = await fetch("/api/design-blender", {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: ac.signal,
        body: JSON.stringify({
          scene,
          projectName: scene.project.name,
          brief,
          planImages: plans,
          references: [...refs, ...concepts.map(({ data, mediaType, name }) => ({ data, mediaType, name }))],
          mode: output === "blender-live" ? "live" : renderMode,
          direction: direction || undefined,
          samples: 64,
        }),
      });
      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({}));
        setError(d?.error || `Request failed (${res.status}).`);
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const ev = JSON.parse(line) as { type: string; label?: string; percent?: number; elapsedMs?: number; error?: string; designUrl?: string } & Partial<BlenderResult>;
          if (ev.type === "progress") {
            setProgress({ chars: 0, label: ev.label ?? "Working…", elapsedMs: ev.elapsedMs ?? 0 });
            if (typeof ev.percent === "number") setPercent(ev.percent);
          } else if (ev.type === "done" && ev.id) {
            onBlenderResult({ id: ev.id, designUrl: ev.designUrl ?? "", stills: ev.stills ?? [], tour: ev.tour, glbUrl: ev.glbUrl, sceneUrl: ev.sceneUrl, live: ev.live });
          } else if (ev.type === "error") {
            setError(ev.designUrl ? `${ev.error}\nDesign script: ${ev.designUrl}` : ev.error || "Blender design failed.");
          }
        }
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") setError("Cancelled.");
      else setError(e instanceof Error ? e.message : "Blender design failed.");
    } finally {
      setBusy(false);
      setProgress(null);
      setPercent(undefined);
      abortRef.current = null;
    }
  }

  async function generate() {
    if (output !== "web") return generateBlender();
    setBusy(true);
    setError(null);
    setProgress({ chars: 0, label: "Sending the plan to the designer…", elapsedMs: 0 });
    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const res = await fetch("/api/design-tour", {
        method: "POST",
        headers: { "content-type": "application/json" },
        signal: ac.signal,
        body: JSON.stringify({
          scene,
          projectName: scene.project.name,
          brief,
          planImages: plans,
          references: [...refs, ...concepts.map(({ data, mediaType, name }) => ({ data, mediaType, name }))],
        }),
      });
      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({}));
        setError(d?.error || `Request failed (${res.status}).`);
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let opened = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const ev = JSON.parse(line) as { type: string; chars?: number; label?: string; elapsedMs?: number; url?: string; error?: string; partialUrl?: string };
          if (ev.type === "progress") setProgress({ chars: ev.chars ?? 0, label: ev.label ?? "Designing…", elapsedMs: ev.elapsedMs ?? 0 });
          else if (ev.type === "done" && ev.url) {
            opened = true;
            onOpen(ev.url);
          } else if (ev.type === "error") {
            setError(ev.partialUrl ? `${ev.error}\nPartial page: ${ev.partialUrl}` : ev.error || "Design failed.");
          }
        }
      }
      if (!opened && !error) {
        const d = await fetch("/api/design-tour").then((r) => r.json()).catch(() => null);
        if (d?.designs) setDesigns(d.designs as DesignMeta[]);
      }
    } catch (e) {
      if ((e as Error)?.name === "AbortError") setError("Cancelled.");
      else setError(e instanceof Error ? e.message : "Design failed.");
    } finally {
      setBusy(false);
      setProgress(null);
      abortRef.current = null;
    }
  }

  const fmtKb = (n: number) => `${(n / 1024).toFixed(0)} KB`;
  const fmtT = (ms: number) => `${Math.floor(ms / 60000)}:${String(Math.floor((ms % 60000) / 1000)).padStart(2, "0")}`;

  return (
    <div style={S.backdrop} onClick={busy ? undefined : onClose}>
      <div style={S.panel} onClick={(e) => e.stopPropagation()}>
        <div style={S.head}>
          <div>
            <div style={S.kicker}>AI INTERIOR DESIGN</div>
            <h2 style={S.h2}>Design {scene.project.name} and build it in 3D</h2>
            <div style={S.sub}>Floor plan (+ brief, optional references) → Claude designs the interior → Blender builds and renders it, or a walkable web tour is written. No images required. Takes a few minutes.</div>
          </div>
          <button style={S.close} onClick={onClose} disabled={busy}>✕</button>
        </div>

        {busy ? (
          <div style={S.progressBox}>
            <div style={S.spinner} />
            <div style={{ fontWeight: 700, marginTop: 10 }}>{progress?.label ?? "Designing…"}</div>
            <div style={S.progMeta}>
              {output === "web" ? `${fmtKb(progress?.chars ?? 0)} written · ` : ""}{fmtT(progress?.elapsedMs ?? 0)} elapsed
              {output === "web" ? " · typically 60–110 KB when complete" : output === "blender-live" ? " · watch your Blender window" : " · Cycles renders take a few minutes"}
            </div>
            <div style={S.progTrack}><div style={{ ...S.progFill, width: `${percent ?? Math.min(96, ((progress?.chars ?? 0) / 85000) * 100)}%` }} /></div>
            <button style={S.ghost} onClick={() => abortRef.current?.abort()}>Cancel</button>
          </div>
        ) : (
          <>
            <div style={S.grid}>
              <section style={S.card}>
                <div style={S.label}>1 · Floor plan page{plans.length === 1 ? "" : "s"} ({plans.length})</div>
                <div style={S.thumbs}>
                  {plans.map((p, i) => (
                    <div key={i} style={S.thumbWrap} title={p.name}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`data:${p.mediaType};base64,${p.data}`} alt={p.name ?? "plan"} style={S.thumb} />
                      <button style={S.thumbX} onClick={() => setPlans((l) => l.filter((_, k) => k !== i))}>✕</button>
                    </div>
                  ))}
                  <button style={S.addBtn} onClick={() => planInput.current?.click()}>+ Add page</button>
                  <input ref={planInput} type="file" accept="image/*" multiple style={{ display: "none" }} onChange={(e) => { void addFiles(e.target.files, "plans"); e.target.value = ""; }} />
                </div>
                <div style={S.hint}>{plans.length ? "The designer reads dimensions, legend and equipment positions from these." : "No plan image attached — the parsed plan data (rooms, walls, legend, fixtures) will be used alone."}</div>
              </section>

              <section style={S.card}>
                <div style={S.label}>2 · Interior references ({refs.length + concepts.length})</div>
                <div style={S.thumbs}>
                  {refs.map((p, i) => (
                    <div key={`r${i}`} style={S.thumbWrap} title={p.name}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`data:${p.mediaType};base64,${p.data}`} alt={p.name ?? "reference"} style={S.thumb} />
                      <button style={S.thumbX} onClick={() => setRefs((l) => l.filter((_, k) => k !== i))}>✕</button>
                    </div>
                  ))}
                  {concepts.map((c, i) => (
                    <div key={`c${i}`} style={S.thumbWrap} title={c.label}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={c.url} alt={c.label} style={S.thumb} />
                      <button style={S.thumbX} onClick={() => setConcepts((l) => l.filter((_, k) => k !== i))}>✕</button>
                    </div>
                  ))}
                  <button style={S.addBtn} onClick={() => refInput.current?.click()}>+ Add images</button>
                  <input ref={refInput} type="file" accept="image/*" multiple style={{ display: "none" }} onChange={(e) => { void addFiles(e.target.files, "refs"); e.target.value = ""; }} />
                </div>
                <div style={S.row}>
                  <button style={S.ghost} disabled={conceptBusy} onClick={() => void generateConcepts()} title="Gemini paints concept views of this café from the plan, your references and the brief">
                    {conceptBusy ? "Painting concepts… (≈1 min)" : "✨ Generate concept images (Gemini)"}
                  </button>
                  <span style={S.hint}>Your photos and mood boards, plus AI concept views. The 3D design follows their palette and mood.</span>
                </div>
                {conceptMsg && <div style={S.warn}>{conceptMsg}</div>}
              </section>
            </div>

            <section style={S.card}>
              <div style={S.label}>3 · Output</div>
              <div style={S.row}>
                {([
                  ["blender", "🏗️ Build in Blender → walk on the web", "Claude designs → Blender builds it → exported as a 3D model you walk through in the browser (optionally photoreal stills / 360° tour too)"],
                  ["blender-live", "🟠 Build in my open Blender", "Pushes the design into the Blender you have open (MCP addon server running on port 9876)"],
                  ["web", "🌐 Web 3D tour (three.js)", "Claude writes a self-contained walkable web page"],
                ] as [OutputKind, string, string][]).map(([k, label, title]) => (
                  <button key={k} style={{ ...S.ghost, ...(output === k ? S.ghostOn : null) }} onClick={() => setOutput(k)} title={title}>{label}</button>
                ))}
              </div>
              {output === "blender" && (
                <div style={{ ...S.row, marginTop: 8 }}>
                  <label style={S.hint}><input type="radio" checked={renderMode === "glb"} onChange={() => setRenderMode("glb")} /> 3D model to walk on the web (fastest)</label>
                  <label style={S.hint}><input type="radio" checked={renderMode === "stills"} onChange={() => setRenderMode("stills")} /> + photoreal stills</label>
                  <label style={S.hint}><input type="radio" checked={renderMode === "both"} onChange={() => setRenderMode("both")} /> + stills and 360° tour</label>
                </div>
              )}
            </section>

            <section style={S.card}>
              <div style={S.label}>4 · Design style</div>
              <select style={{ ...S.textarea, height: "auto", marginBottom: 8 }} value={direction} onChange={(e) => setDirection(e.target.value)}>
                <option value="">✨ Surprise me: a different design every run</option>
                {DIRECTIONS.map((d) => <option key={d.id} value={d.id}>{d.name}: {d.summary}</option>)}
              </select>
              <textarea style={S.textarea} rows={3} placeholder="Optional brief: colours, brand, anything you want (overrides the style)" value={brief} onChange={(e) => setBrief(e.target.value)} />
            </section>

            {error && <div style={S.error}>{error}</div>}

            <div style={S.actions}>
              <button style={S.primary} disabled={conceptBusy} onClick={() => void generate()}>
                {output === "web" ? "🎨 Design & build the web 3D tour" : output === "blender-live" ? "🏗️ Design & build in my Blender" : "🏗️ Design & build in Blender"}
              </button>
              <button style={S.ghost} disabled={conceptBusy} onClick={() => void runAll()} title="Optional: paint Gemini concept images first (needs a billed Gemini key), then design">✨ Concepts first, then design</button>
            </div>
            <div style={S.hint}>Design: Claude (claude-opus-5-5), ≈ 3–6 min. Blender build + 3D export ≈ 1 min; photoreal stills add 1–3 min per view on CPU. No images needed.</div>

            {blenderDesigns.length > 0 && (
              <section style={S.card}>
                <div style={S.label}>Previous Blender designs</div>
                <div style={S.list}>
                  {blenderDesigns.map((d) => (
                    <button key={d.id} style={S.listItem} onClick={() => onBlenderResult({ id: d.id, designUrl: d.designUrl, stills: d.stills ?? [], tour: d.tour, glbUrl: d.glbUrl, sceneUrl: d.sceneUrl })} title={d.designUrl}>
                      <span style={{ fontWeight: 700 }}>{d.projectName}</span>
                      <span style={S.listMeta}>{new Date(d.createdAt).toLocaleString()}{d.glbUrl ? " · walkable 3D" : ""} · {(d.stills ?? []).length} stills{d.tour ? " · 360° tour" : ""}{d.complete ? "" : " · incomplete"}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {designs.length > 0 && (
              <section style={S.card}>
                <div style={S.label}>Previous web tours</div>
                <div style={S.list}>
                  {designs.map((d) => (
                    <button key={d.id} style={S.listItem} onClick={() => onOpen(d.url)} title={d.brief}>
                      <span style={{ fontWeight: 700 }}>{d.projectName}</span>
                      <span style={S.listMeta}>{new Date(d.createdAt).toLocaleString()} · {fmtKb(d.chars)} · {d.model}{d.complete ? "" : " · incomplete"}</span>
                    </button>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}

const S: Record<string, CSSProperties> = {
  backdrop: { position: "fixed", inset: 0, background: "rgba(20,14,10,0.55)", display: "grid", placeItems: "center", zIndex: 1200, padding: 20, backdropFilter: "blur(3px)" },
  panel: { background: "#f8f4ec", color: "#2f2119", borderRadius: 16, width: "min(880px, 96vw)", maxHeight: "92vh", overflowY: "auto", padding: 20, boxShadow: "0 16px 60px rgba(0,0,0,0.4)", fontFamily: "system-ui, sans-serif" },
  head: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, marginBottom: 12 },
  kicker: { fontSize: 10, letterSpacing: 1.5, fontWeight: 700, color: "#9a6b2f" },
  h2: { fontSize: 20, margin: "4px 0 4px", fontWeight: 600 },
  sub: { fontSize: 13, color: "#6e5a4a", lineHeight: 1.45 },
  close: { border: 0, background: "transparent", fontSize: 18, cursor: "pointer", color: "#6e5a4a" },
  grid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 },
  card: { background: "#fff", border: "1px solid #e6dccb", borderRadius: 12, padding: 12, marginTop: 12 },
  label: { fontSize: 12, fontWeight: 700, color: "#6e5a4a", marginBottom: 8 },
  thumbs: { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" },
  thumbWrap: { position: "relative", width: 96, height: 72, borderRadius: 8, overflow: "hidden", border: "1px solid #e6dccb", background: "#eee" },
  thumb: { width: "100%", height: "100%", objectFit: "cover", display: "block" },
  thumbX: { position: "absolute", top: 3, right: 3, width: 20, height: 20, borderRadius: 10, border: 0, background: "rgba(0,0,0,0.55)", color: "#fff", fontSize: 11, cursor: "pointer" },
  addBtn: { width: 96, height: 72, borderRadius: 8, border: "1px dashed #c9b89b", background: "#fffaf3", color: "#9a6b2f", fontSize: 12, fontWeight: 600, cursor: "pointer" },
  hint: { fontSize: 11.5, color: "#8a7a68", marginTop: 6, lineHeight: 1.4 },
  row: { display: "flex", alignItems: "center", gap: 10, marginTop: 8, flexWrap: "wrap" },
  warn: { marginTop: 8, fontSize: 12, color: "#8a5a1e", background: "#fff3e0", padding: "7px 10px", borderRadius: 7 },
  textarea: { width: "100%", boxSizing: "border-box", border: "1px solid #e6dccb", borderRadius: 8, padding: 10, fontSize: 13, lineHeight: 1.45, fontFamily: "inherit", color: "#2f2119", resize: "vertical" },
  error: { marginTop: 12, fontSize: 12.5, color: "#c0392b", background: "#fbeceb", padding: "8px 10px", borderRadius: 8, whiteSpace: "pre-wrap" },
  actions: { display: "flex", alignItems: "center", gap: 12, marginTop: 14, flexWrap: "wrap" },
  primary: { border: 0, background: "#9a6a3a", color: "#fff", padding: "11px 18px", borderRadius: 10, fontSize: 14, fontWeight: 700, cursor: "pointer" },
  ghost: { border: "1px solid #c9b89b", background: "#fffaf3", color: "#5b4a3a", padding: "7px 12px", borderRadius: 8, fontSize: 12.5, cursor: "pointer", fontWeight: 600 },
  ghostOn: { background: "#3a271b", color: "#f4eadb", border: "1px solid #3a271b" },
  list: { display: "flex", flexDirection: "column", gap: 6 },
  listItem: { textAlign: "left", display: "flex", flexDirection: "column", gap: 2, border: "1px solid #e6dccb", background: "#fffdf9", borderRadius: 8, padding: "8px 10px", cursor: "pointer", color: "#2f2119", fontSize: 13 },
  listMeta: { fontSize: 11.5, color: "#8a7a68" },
  progressBox: { textAlign: "center", padding: "26px 20px" },
  spinner: { width: 32, height: 32, margin: "0 auto", border: "3px solid #e3ddd1", borderTopColor: "#9a6b2f", borderRadius: "50%", animation: "cvspin 0.9s linear infinite" },
  progMeta: { fontSize: 12.5, color: "#6e5a4a", marginTop: 6 },
  progTrack: { width: "100%", height: 8, borderRadius: 999, background: "#e9e2d4", overflow: "hidden", margin: "12px 0 14px" },
  progFill: { height: "100%", borderRadius: 999, background: "linear-gradient(90deg,#b5762f,#d9ab72)", transition: "width 0.5s ease" },
};
