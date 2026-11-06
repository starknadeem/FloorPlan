"use client";

// "Gallery" (3D renders) and "AI images" (verified retouches of those renders): two buttons and one full-screen
// viewer. The hook loads every image into the browser as soon as a design opens, so the viewer opens instantly.

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import type { ImageItem, ImageManifest } from "@/lib/design-images/job";

type Tab = "renders" | "ai";
interface Data {
  manifest: ImageManifest | null;
  stills: { url: string; label: string }[];
  running: boolean;
  aiEnabled: boolean;
}

// keeps decoded images alive for the session; a dropped Image object could be evicted from the browser cache
const cache = new Map<string, HTMLImageElement>();
const queue: string[] = [];
let loading = 0;
function pump() {
  while (loading < 4 && queue.length) {
    const src = queue.shift()!;
    const img = new Image();
    img.decoding = "async";
    img.fetchPriority = "low"; // never competes with the 3D model
    loading++;
    const end = () => {
      loading--;
      pump();
    };
    img.onload = end;
    img.onerror = () => {
      cache.delete(src);
      end();
    };
    img.src = src;
    cache.set(src, img);
  }
}
function preload(urls: (string | undefined)[]) {
  for (const u of urls) {
    if (u && !cache.has(u) && !queue.includes(u)) queue.push(u);
  }
  pump();
}

export function useDesignImages(designId: string | undefined) {
  const [data, setData] = useState<Data | null>(null);

  const refresh = useCallback(async () => {
    if (!designId) return null;
    const r = await fetch(`/api/design-images?id=${encodeURIComponent(designId)}`, { cache: "no-store" });
    if (!r.ok) return null;
    const d = (await r.json()) as Data;
    setData(d);
    preload([...d.stills.map((s) => s.url), ...(d.manifest?.items ?? []).flatMap((i) => [i.render, i.ai])]);
    return d;
  }, [designId]);

  const running = Boolean(data?.running);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = async () => {
      const d = await refresh().catch(() => null);
      if (live && d?.running) timer = setTimeout(() => void tick(), 8000);
    };
    void tick();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, [refresh, running]);

  const start = useCallback(async () => {
    if (!designId) return;
    await fetch("/api/design-images", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: designId }) });
    await refresh();
  }, [designId, refresh]);

  return { data, start };
}

interface Shot {
  key: string;
  area: string;
  label: string;
  src: string;
  compare?: string;
}

function shotsFor(tab: Tab, data: Data | null): Shot[] {
  const items: ImageItem[] = data?.manifest?.items ?? [];
  if (tab === "ai") return items.filter((i) => i.ai && i.render).map((i) => ({ key: i.id, area: i.area, label: i.label, src: i.ai!, compare: i.render }));
  const rendered = items.filter((i) => i.render).map((i) => ({ key: i.id, area: i.area, label: i.label, src: i.render! }));
  const stills = (data?.stills ?? []).map((s) => ({ key: s.url, area: "Designer views", label: s.label, src: s.url }));
  return [...rendered, ...stills];
}

function Overlay({ tab, setTab, data, start, projectName, onClose }: { tab: Tab; setTab: (t: Tab) => void; data: Data | null; start: () => Promise<void>; projectName: string; onClose: () => void }) {
  const [area, setArea] = useState("All");
  const [open, setOpen] = useState<number | null>(null);
  const [showSource, setShowSource] = useState(false);

  const all = useMemo(() => shotsFor(tab, data), [tab, data]);
  const areas = useMemo(() => ["All", ...Array.from(new Set(all.map((s) => s.area)))], [all]);
  const activeArea = areas.includes(area) ? area : "All";
  const shown = useMemo(() => all.filter((s) => activeArea === "All" || s.area === activeArea), [all, activeArea]);
  const current = open != null ? shown[open] : null;

  // the walkthrough listens to the keyboard on window: keep keys here while this is up
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      e.stopImmediatePropagation();
      if (e.key === "Escape") {
        if (open != null) setOpen(null);
        else onClose();
      }
      if (open != null && shown.length && e.key === "ArrowRight") setOpen((open + 1) % shown.length);
      if (open != null && shown.length && e.key === "ArrowLeft") setOpen((open - 1 + shown.length) % shown.length);
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [open, shown.length, onClose]);

  const m = data?.manifest;
  const items = m?.items ?? [];
  const planned = items.length;
  const rendered = items.filter((i) => i.render).length;
  const verified = items.filter((i) => i.aiStatus === "verified").length;
  const rejected = items.filter((i) => i.aiStatus === "rejected").length;
  const unfinished = items.filter((i) => i.aiStatus === "failed" || i.aiStatus === "unverified").length;
  const running = Boolean(data?.running);
  const canStart = !running && (planned === 0 || rendered < planned || (Boolean(data?.aiEnabled) && verified + rejected < planned));

  return createPortal(
    <div style={S.wrap} onPointerDown={(e) => e.stopPropagation()} role="dialog" aria-label={tab === "ai" ? "AI images" : "Gallery"}>
      <div style={S.head}>
        <div>
          <div style={S.tabsRow}>
            <button style={{ ...S.title, ...(tab === "renders" ? S.titleOn : null) }} onClick={() => { setTab("renders"); setOpen(null); }}>Gallery</button>
            <button style={{ ...S.title, ...(tab === "ai" ? S.titleOn : null) }} onClick={() => { setTab("ai"); setOpen(null); }}>AI images</button>
          </div>
          <div style={S.sub}>
            {projectName} · {all.length} image{all.length === 1 ? "" : "s"}
            {tab === "ai" ? " · retouched from the 3D renders and checked against them" : " · rendered from the 3D model"}
          </div>
        </div>
        <div style={S.headActions}>
          {canStart && <button style={S.primary} onClick={() => void start()}>{planned ? "Continue generating" : "Generate images"}</button>}
          <button style={S.btn} onClick={onClose}>Close</button>
        </div>
      </div>

      {running && (
        <div style={S.note}>
          {m?.phase ?? "Working…"}
          {planned > 0 ? ` · ${rendered}/${planned} rendered · ${verified} AI images ready` : ""}
          <span style={{ opacity: 0.7 }}> · This runs in the background; you can close this and keep walking.</span>
        </div>
      )}
      {m?.aiBlocked && (
        <div style={{ ...S.note, ...S.bad }}>
          {m.aiBlocked} No AI images can be made until this is fixed. Update OPENAI_API_KEY in webapp/.env.local and restart the app, then press Continue generating here. Finished renders are kept.
        </div>
      )}
      {data && !data.aiEnabled && tab === "ai" && <div style={{ ...S.note, ...S.bad }}>OPENAI_API_KEY is not set in webapp/.env.local.</div>}
      {m?.error && <div style={{ ...S.note, ...S.bad }}>{m.error}</div>}
      {tab === "ai" && rejected > 0 && <div style={S.note}>{rejected} AI image{rejected === 1 ? " was" : "s were"} rejected and hidden because {rejected === 1 ? "it" : "they"} changed what is in the 3D model.</div>}
      {tab === "ai" && unfinished > 0 && !running && <div style={S.note}>{unfinished} image{unfinished === 1 ? "" : "s"} could not be finished or checked. Press Continue generating to retry.</div>}

      {areas.length > 2 && (
        <div style={S.tabs}>
          {areas.map((a) => (
            <button key={a} style={{ ...S.tab, ...(a === activeArea ? S.tabOn : null) }} onClick={() => { setArea(a); setOpen(null); }}>{a}</button>
          ))}
        </div>
      )}

      <div style={S.grid}>
        {!data && <div style={S.empty}>Loading…</div>}
        {data && !all.length && <div style={S.empty}>{tab === "ai" ? (running ? "AI images will appear here as they pass the check." : "No AI images yet.") : running ? "Renders will appear here as they finish." : "No images yet. Press Generate images."}</div>}
        {shown.map((s, i) => (
          <button key={s.key} style={S.card} onClick={() => { setOpen(i); setShowSource(false); }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={s.src} alt={s.label} style={S.thumb} decoding="async" />
            <span style={S.cap}>{s.label}</span>
          </button>
        ))}
      </div>

      {current && (
        <div style={S.light} onClick={() => setOpen(null)}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={showSource && current.compare ? current.compare : current.src} alt={current.label} style={S.big} onClick={(e) => e.stopPropagation()} />
          <div style={S.lightBar} onClick={(e) => e.stopPropagation()}>
            <button style={S.btn} onClick={() => setOpen(((open ?? 0) - 1 + shown.length) % shown.length)}>‹ Previous</button>
            <span style={S.lightCap}>{current.label} · {current.compare && !showSource ? "AI image" : "3D render"}</span>
            {current.compare && <button style={S.btn} onClick={() => setShowSource((v) => !v)}>{showSource ? "Show AI image" : "Compare with 3D"}</button>}
            <button style={S.btn} onClick={() => setOpen(((open ?? 0) + 1) % shown.length)}>Next ›</button>
            <button style={S.btn} onClick={() => setOpen(null)}>Back</button>
          </div>
        </div>
      )}
    </div>,
    document.body,
  );
}

/** The Gallery and AI images buttons. Mounting this is what starts preloading. */
export default function GalleryButtons({ designId, projectName, buttonStyle }: { designId: string; projectName: string; buttonStyle: CSSProperties }) {
  const { data, start } = useDesignImages(designId);
  const [tab, setTab] = useState<Tab | null>(null);
  const aiCount = (data?.manifest?.items ?? []).filter((i) => i.ai).length;
  const close = useCallback(() => setTab(null), []);
  return (
    <>
      <button style={buttonStyle} onClick={() => setTab("renders")} title="Renders of every area from several angles">Gallery</button>
      <button style={buttonStyle} onClick={() => setTab("ai")} title="ChatGPT images made from the 3D renders">AI images{aiCount ? ` (${aiCount})` : ""}</button>
      {tab && <Overlay tab={tab} setTab={setTab} data={data} start={start} projectName={projectName} onClose={close} />}
    </>
  );
}

const S: Record<string, CSSProperties> = {
  wrap: { position: "fixed", inset: 0, zIndex: 1000, background: "rgba(20,16,13,0.98)", color: "#f2ebe0", display: "flex", flexDirection: "column", padding: 20, gap: 12, overflow: "hidden", fontFamily: "system-ui, -apple-system, 'Segoe UI', sans-serif" },
  head: { display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" },
  headActions: { display: "flex", gap: 8, flexWrap: "wrap" },
  tabsRow: { display: "flex", gap: 6, marginLeft: -10 },
  title: { fontSize: 22, fontWeight: 500, background: "transparent", color: "#f2ebe0", opacity: 0.55, borderWidth: 0, borderRadius: 10, padding: "4px 10px", cursor: "pointer" },
  titleOn: { opacity: 1, fontWeight: 600 },
  sub: { fontSize: 13, opacity: 0.7, marginTop: 2 },
  btn: { borderWidth: 1, borderStyle: "solid", borderColor: "rgba(255,255,255,0.25)", background: "rgba(255,255,255,0.08)", color: "#f2ebe0", borderRadius: 999, padding: "8px 14px", fontSize: 13.5, cursor: "pointer", whiteSpace: "nowrap" },
  primary: { borderWidth: 0, background: "#9a6a3a", color: "#fff", borderRadius: 999, padding: "8px 16px", fontSize: 13.5, fontWeight: 600, cursor: "pointer" },
  note: { background: "rgba(255,255,255,0.08)", borderRadius: 10, padding: "8px 12px", fontSize: 13.5, lineHeight: 1.45 },
  bad: { background: "#5a2a22" },
  tabs: { display: "flex", gap: 6, flexWrap: "wrap" },
  tab: { borderWidth: 1, borderStyle: "solid", borderColor: "rgba(255,255,255,0.2)", background: "transparent", color: "#f2ebe0", borderRadius: 999, padding: "6px 12px", fontSize: 13, cursor: "pointer" },
  tabOn: { background: "#f2ebe0", color: "#20170f" },
  grid: { flex: 1, overflowY: "auto", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12, alignContent: "start" },
  card: { borderWidth: 0, padding: 0, background: "transparent", color: "inherit", cursor: "pointer", textAlign: "left" },
  thumb: { width: "100%", aspectRatio: "3 / 2", objectFit: "cover", borderRadius: 10, display: "block", background: "#2a221c" },
  cap: { display: "block", fontSize: 13, padding: "6px 2px", opacity: 0.85 },
  empty: { gridColumn: "1 / -1", padding: 40, textAlign: "center", opacity: 0.7 },
  light: { position: "absolute", inset: 0, background: "rgba(10,8,6,0.98)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 16, gap: 12 },
  big: { maxWidth: "100%", maxHeight: "calc(100% - 70px)", objectFit: "contain", borderRadius: 8 },
  lightBar: { display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "center" },
  lightCap: { fontSize: 14, padding: "0 10px" },
};
