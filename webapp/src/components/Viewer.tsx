"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState, useSyncExternalStore, type CSSProperties } from "react";
import type { CafeScene, Fixture } from "@/types/cafescene";
import { coffeeBerryScene } from "@/data/coffeeBerry";
import { sampleParsedScene } from "@/data/sampleParsed";
import Welcome from "@/components/Welcome";
import type { ViewMode } from "@/components/scene/Controls";
import type { CaptureApi } from "@/components/scene/CafeCanvas";
import PlanEditor from "@/components/PlanEditor";
import { applyStyle, STYLE_PRESETS } from "@/lib/design/palette";
import type { TourStop } from "@/components/tour/TourViewer";
import { buildTourModel } from "@/lib/tour/model";
import DesignTourPanel, { fileToImageIn, type BlenderResult, type ImageIn } from "@/components/DesignTourPanel";
import { TourStore } from "@/lib/tour/store";

const CafeCanvas = dynamic(() => import("@/components/scene/CafeCanvas"), {
  ssr: false,
  loading: () => (
    <div style={styles.loading}>
      <div>Loading 3D café…</div>
    </div>
  ),
});

const TourViewer = dynamic(() => import("@/components/tour/TourViewer"), { ssr: false });
const WalkOverlay = dynamic(() => import("@/components/tour/WalkOverlay"), { ssr: false });
const BlenderWalkViewer = dynamic(() => import("@/components/tour/BlenderWalkViewer"), { ssr: false });

const noSubscribe = () => () => {};

interface ParseMeta {
  model: string;
  usage: { input_tokens: number; output_tokens: number };
  estCostUsd: number;
  elapsedMs: number;
  counts: Record<string, number>;
}

export default function Viewer() {
  const [scene, setScene] = useState<CafeScene>(coffeeBerryScene);
  const [sceneKey, setSceneKey] = useState(0);
  const [source, setSource] = useState<"sample" | "parsed">("sample");
  const [mode, setMode] = useState<ViewMode>("orbit");
  const [view, setView] = useState<"3d" | "edit">("3d");
  const [selected, setSelected] = useState<Fixture | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meta, setMeta] = useState<ParseMeta | null>(null);
  const [showIssues, setShowIssues] = useState(true);
  const [style, setStyle] = useState<string>(coffeeBerryScene.design?.style ?? "industrial-chic");
  const [styleBusy, setStyleBusy] = useState(false);
  const [arrangeBusy, setArrangeBusy] = useState(false);
  const [designNote, setDesignNote] = useState<string | null>(null);
  const [renderMsg, setRenderMsg] = useState<string | null>(null);
  const [renderBusy, setRenderBusy] = useState(false);
  const [renderImg, setRenderImg] = useState<string | null>(null);
  const [tour, setTour] = useState<{ baseUrl: string; stops: TourStop[] } | null>(null);
  const [tourBusy, setTourBusy] = useState(false);
  const [tourProgress, setTourProgress] = useState<{ percent: number; label: string } | null>(null);
  const tourAbort = useRef<AbortController | null>(null);
  const [started, setStarted] = useState(false);
  // AI design tour (the claude.ai flow): plan image(s) kept from the upload, panel + result viewer.
  const [planImages, setPlanImages] = useState<ImageIn[]>([]);
  const [designPanel, setDesignPanel] = useState(false);
  const [designUrl, setDesignUrl] = useState<string | null>(null);
  const [blenderResult, setBlenderResult] = useState<BlenderResult | null>(null);
  const [blenderWalk, setBlenderWalk] = useState<{ glbUrl: string; sceneUrl: string } | null>(null);
  const [lightbox, setLightbox] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const captureApi = useRef<CaptureApi | null>(null);

  // Walk mode: collision + stops + narration derived from the current scene (cheap, rebuilt on change).
  const walkStore = useMemo(() => (mode === "walk" ? new TourStore(buildTourModel(scene)) : null), [mode, scene]);
  useEffect(() => () => walkStore?.dispose(), [walkStore]);
  useSyncExternalStore(walkStore ? walkStore.subscribe : noSubscribe, () => walkStore?.version ?? 0, () => 0);
  const evening = walkStore?.evening ?? false;

  const stats = {
    rooms: scene.rooms.length,
    walls: scene.walls.length,
    openings: scene.openings.length,
    fixtures: scene.fixtures.length,
  };

  function loadScene(next: CafeScene, src: "sample" | "parsed") {
    setScene(applyStyle(next, style)); // System 2: apply interior design (materials, lighting)
    setSource(src);
    setSelected(null);
    setSceneKey((k) => k + 1); // remount canvas -> reframe camera
  }

  function changeStyle(k: string) {
    setStyle(k);
    setScene((s) => applyStyle(s, k));
  }

  async function aiDesign() {
    setStyleBusy(true);
    setDesignNote(null);
    setError(null);
    try {
      const summary =
        `Coffee shop. Rooms: ${scene.rooms.map((r) => `${r.name} (${r.category})`).join(", ")}. ` +
        `Fixtures: ${scene.fixtures.length}. Project: ${scene.project.name}.`;
      const res = await fetch("/api/design", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ summary }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.error || "Design request failed");
      changeStyle(d.style);
      setDesignNote(`${STYLE_PRESETS[d.style]?.name ?? d.style}${d.rationale ? " — " + d.rationale : ""}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Design failed");
    } finally {
      setStyleBusy(false);
    }
  }

  async function aiArrange() {
    setArrangeBusy(true);
    setDesignNote(null);
    setError(null);
    try {
      const res = await fetch("/api/layout", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scene }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d?.error || "Arrange request failed");
      // keep current style/materials applied, remount to reframe
      setScene(applyStyle(d.scene as CafeScene, style));
      setSelected(null);
      setSceneKey((k) => k + 1);
      const extra = d.added ? ` (+${d.added} WC fixtures)` : "";
      setDesignNote(`${d.note ?? "Arranged."}${extra}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Arrange failed");
    } finally {
      setArrangeBusy(false);
    }
  }

  async function handleFile(file: File) {
    setStarted(true);
    setError(null);
    setMeta(null);
    // client-side validation (friendly errors before spending an API call)
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) {
      setError(
        file.type === "application/pdf"
          ? "PDFs aren't supported yet — please export the plan page as a PNG or JPG and upload that."
          : "Unsupported file. Please upload a PNG, JPG, or WEBP image of a floor plan.",
      );
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setError("That image is larger than 25 MB. Please upload a smaller version.");
      return;
    }

    setBusy(true);
    try {
      const planImg = await fileToImageIn(file);
      setPlanImages(planImg ? [planImg] : []);
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/parse", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
      const parsed = data.scene as CafeScene;
      if (!parsed.walls || parsed.walls.length < 2) {
        setError(
          "We couldn't detect a clear floor plan in that image. Try a top-down architectural plan with visible walls and dimensions.",
        );
        return;
      }
      setMeta(data.meta as ParseMeta);
      setShowIssues(true);
      // Auto-furnish: fill every room with the equipment it's missing (WC → toilet/basin/mirror,
      // kitchen → stove/hood/fridge, counter → espresso/grinder/POS, seating → chairs, …) using
      // the same engine as the "AI arrange" button. A parsed plan rarely draws every appliance,
      // so without this the rooms render half-empty. Falls back to the raw parse if it fails.
      let furnished = parsed;
      try {
        const lres = await fetch("/api/layout", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ scene: parsed }),
        });
        if (lres.ok) {
          const ld = await lres.json();
          if (ld?.scene?.fixtures) furnished = ld.scene as CafeScene;
        }
      } catch {
        /* keep the un-furnished parse */
      }
      loadScene(furnished, "parsed");
      // Next step of the flow: references + brief → Claude designs the café and writes the 3D tour.
      setDesignPanel(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Parsing failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function downloadDataUrl(url: string, name: string) {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
  }

  function downloadPng() {
    const url = captureApi.current?.capture();
    if (url) downloadDataUrl(url, `${scene.project.name.replace(/\W+/g, "_")}.png`);
  }

  function dollhouse() {
    captureApi.current?.isometric();
    setRenderMsg("Isometric dollhouse view — use “Download PNG” to export it.");
  }

  async function aiPhotoreal() {
    const image = captureApi.current?.capture();
    if (!image) return;
    setRenderBusy(true);
    setRenderMsg(null);
    try {
      const res = await fetch("/api/render", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          image,
          prompt:
            `Photorealistic architectural visualization of a modern Coffee Berry specialty coffee shop, ` +
            `${scene.design?.style ?? "contemporary"} style. Terrazzo and grey stone counters, marble ` +
            `table tops on black pedestals, warm wood veneer shelving, polished concrete floor, cream ` +
            `walls, black 3-group espresso machine, glass pastry display cases, pendant lighting, potted ` +
            `olive trees, branded umbrellas on the terrace. Soft daylight, clean interior-design render, ` +
            `high detail, realistic materials and reflections. Keep the existing layout and camera.`,
        }),
      });
      const d = await res.json();
      if (res.status === 501) {
        setRenderMsg(d.error);
      } else if (!res.ok) {
        setRenderMsg(d?.error || "Render failed.");
      } else if (d.imageUrl) {
        window.open(d.imageUrl, "_blank");
      }
    } catch (e) {
      setRenderMsg(e instanceof Error ? e.message : "Render failed");
    } finally {
      setRenderBusy(false);
    }
  }

  async function blenderRender() {
    const pose = captureApi.current?.cameraPose();
    setRenderBusy(true);
    setRenderMsg("Rendering in Blender (Cycles)… this can take 10–60s.");
    try {
      const res = await fetch("/api/render/blender", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          scene,
          cam: pose ? [...pose.position, ...pose.target] : undefined,
          samples: 96,
          res: [1600, 900],
          ceiling: false, // dollhouse: open roof so the furnished interior is visible
        }),
      });
      const d = await res.json();
      if (res.status === 501) {
        setRenderMsg(d.error);
      } else if (!res.ok) {
        setRenderMsg(d?.detail ? `${d.error}\n${d.detail}` : d?.error || "Blender render failed.");
      } else if (d.imageUrl) {
        setRenderImg(d.imageUrl);
        setRenderMsg(null);
      }
    } catch (e) {
      setRenderMsg(e instanceof Error ? e.message : "Blender render failed");
    } finally {
      setRenderBusy(false);
    }
  }

  function cancelTour() {
    tourAbort.current?.abort();
  }

  async function generateTour(sceneArg?: CafeScene) {
    const useScene = sceneArg ?? scene;
    const ac = new AbortController();
    tourAbort.current = ac;
    setTourBusy(true);
    setTourProgress({ percent: 0, label: "Starting Blender…" });
    setRenderMsg(null);
    try {
      const res = await fetch("/api/tour", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ scene: useScene }),
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        const d = await res.json().catch(() => ({}));
        setRenderMsg(d?.error || `Tour request failed (${res.status}).`);
        return;
      }
      // read the NDJSON progress stream
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let opened = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let i;
        while ((i = buf.indexOf("\n")) >= 0) {
          const line = buf.slice(0, i).trim();
          buf = buf.slice(i + 1);
          if (!line) continue;
          const ev = JSON.parse(line) as {
            type: string;
            percent?: number;
            label?: string;
            error?: string;
            detail?: string;
            baseUrl?: string;
            stops?: TourStop[];
          };
          if (ev.type === "progress") {
            setTourProgress({ percent: ev.percent ?? 0, label: ev.label ?? "Rendering…" });
          } else if (ev.type === "done" && ev.stops?.length) {
            setTourProgress({ percent: 100, label: "Opening tour…" });
            setTour({ baseUrl: ev.baseUrl!, stops: ev.stops });
            opened = true;
          } else if (ev.type === "error") {
            setRenderMsg(ev.detail ? `${ev.error}\n${ev.detail}` : ev.error || "Tour render failed.");
          }
        }
      }
      if (!opened && !tour) setRenderMsg((m) => m ?? "Tour render produced no panoramas.");
    } catch (e) {
      if ((e as Error)?.name === "AbortError") {
        setRenderMsg("Tour cancelled. (Blender may keep rendering in the background.)");
      } else {
        setRenderMsg(e instanceof Error ? e.message : "Tour render failed");
      }
    } finally {
      setTourBusy(false);
      setTourProgress(null);
      tourAbort.current = null;
    }
  }

  if (tour) {
    return (
      <TourViewer
        stops={tour.stops}
        baseUrl={tour.baseUrl}
        projectName={scene.project.name}
        onExit={() => setTour(null)}
      />
    );
  }

  if (blenderWalk) {
    return (
      <div style={styles.root}>
        <BlenderWalkViewer glbUrl={blenderWalk.glbUrl} sceneUrl={blenderWalk.sceneUrl} projectName={scene.project.name} onExit={() => setBlenderWalk(null)} />
      </div>
    );
  }

  if (blenderResult) {
    const r = blenderResult;
    return (
      <div style={{ ...styles.root, background: "#141110", overflowY: "auto" }}>
        <div style={styles.designBar}>
          <span style={styles.designBadge}>🏗️ AI design in Blender · {scene.project.name}</span>
          {r.glbUrl && r.sceneUrl && (
            <button style={{ ...styles.designLink, background: "#9a6a3a", border: "1px solid transparent", fontWeight: 700 }} onClick={() => setBlenderWalk({ glbUrl: r.glbUrl!, sceneUrl: r.sceneUrl! })}>🚶 Walk it on the web</button>
          )}
          {r.tour && r.tour.stops.length > 0 && (
            <button style={styles.designLink} onClick={() => setTour({ baseUrl: r.tour!.baseUrl, stops: r.tour!.stops as TourStop[] })}>🎬 Walk the 360° tour</button>
          )}
          <a style={styles.designLink} href={r.designUrl} download>Download design.py</a>
          <button style={styles.designLink} onClick={() => { setBlenderResult(null); setDesignPanel(true); }}>New design</button>
          <button style={styles.designExit} onClick={() => setBlenderResult(null)}>✕ Exit</button>
        </div>
        <div style={styles.gallery}>
          {r.live && (
            <div style={styles.galleryNote}>Built in your open Blender. Output: <code>{r.live}</code></div>
          )}
          {r.stills.map((s) => (
            <figure key={s.url} style={styles.galleryItem} onClick={() => setLightbox(s.url)}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={s.url} alt={s.label} style={styles.galleryImg} />
              <figcaption style={styles.galleryCap}>{s.label}</figcaption>
            </figure>
          ))}
          {!r.stills.length && !r.live && (
            <div style={styles.galleryNote}>{r.glbUrl ? "The café was built in Blender and exported as a 3D model. Use “Walk it on the web” above, or re-run with photoreal stills." : "No renders in this result."}</div>
          )}
        </div>
        {lightbox && (
          <div style={styles.renderOverlay} onClick={() => setLightbox(null)}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={lightbox} alt="render" style={styles.renderImage} />
          </div>
        )}
      </div>
    );
  }

  if (designUrl) {
    return (
      <div style={styles.root}>
        <iframe src={designUrl} title="AI design tour" style={{ position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, background: "#1c1511" }} allow="fullscreen" />
        <div style={styles.designBar}>
          <span style={styles.designBadge}>🎨 AI design tour · {scene.project.name}</span>
          <a style={styles.designLink} href={designUrl} target="_blank" rel="noreferrer">Open in new tab</a>
          <a style={styles.designLink} href={designUrl} download={`${scene.project.name.replace(/\W+/g, "_")}_tour.html`}>Download HTML</a>
          <button style={styles.designLink} onClick={() => { setDesignUrl(null); setDesignPanel(true); }}>New design</button>
          <button style={styles.designExit} onClick={() => setDesignUrl(null)}>✕ Exit</button>
        </div>
      </div>
    );
  }

  if (mode === "walk" && walkStore) {
    return (
      <div style={styles.root}>
        <CafeCanvas key={sceneKey} scene={scene} mode="walk" selectedId={null} onSelect={() => {}} tour={walkStore} evening={evening} />
        <WalkOverlay
          store={walkStore}
          projectName={scene.project.name}
          subtitle={`${stats.rooms} rooms · ${stats.fixtures} fixtures · walkable model`}
          onExit={() => setMode("orbit")}
        />
      </div>
    );
  }

  const issues = scene.issues ?? [];
  const errCount = issues.filter((i) => i.severity === "error").length;
  const warnCount = issues.filter((i) => i.severity === "warning").length;

  if (view === "edit") {
    return (
      <PlanEditor
        scene={scene}
        onApply={(s) => {
          setScene(s);
          setSelected(null);
          setSceneKey((k) => k + 1);
          setView("3d");
        }}
        onCancel={() => setView("3d")}
      />
    );
  }

  return (
    <div
      style={styles.root}
      onDragOver={(e) => {
        if (!started) return;
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => {
        if (started) setDragOver(false);
      }}
      onDrop={(e) => {
        if (!started) return;
        e.preventDefault();
        setDragOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) handleFile(f);
      }}
    >
      <CafeCanvas
        key={sceneKey}
        scene={scene}
        mode={mode}
        selectedId={selected?.id ?? null}
        onSelect={setSelected}
        captureApi={captureApi}
      />

      {!started && (
        <Welcome
          onPickFile={handleFile}
          onSampleCafe={() => {
            loadScene(coffeeBerryScene, "sample");
            setStarted(true);
          }}
          onParsedSample={() => {
            loadScene(sampleParsedScene, "parsed");
            setStarted(true);
            const src = sampleParsedScene.pages?.[0]?.sourceFile;
            if (src) {
              fetch(`/plans/${encodeURIComponent(src)}`)
                .then((r) => (r.ok ? r.blob() : null))
                .then((b) => (b ? fileToImageIn(new File([b], src, { type: b.type || "image/jpeg" })) : null))
                .then((img) => setPlanImages(img ? [img] : []))
                .catch(() => {});
            }
          }}
          onClose={() => setStarted(true)}
          error={error}
        />
      )}

      {dragOver && (
        <div style={styles.dnd}>
          <div style={styles.dndCard}>⬆️ Drop your floor plan to upload</div>
        </div>
      )}

      {/* Title / info card */}
      <div style={styles.topLeft}>
        <div style={styles.badge}>
          PHASE 2 · {source === "parsed" ? "AI-PARSED PLAN" : "SAMPLE SCENE"}
        </div>
        <h1 style={styles.title}>{scene.project.name}</h1>
        <div style={styles.sub}>
          {stats.rooms} rooms · {stats.walls} walls · {stats.openings} openings · {stats.fixtures} fixtures
          {source === "parsed" && (
            <> · overall confidence {Math.round(scene.project.confidenceOverall * 100)}%</>
          )}
        </div>
        <div style={styles.actions}>
          <button style={styles.primaryBtn} disabled={busy} onClick={() => fileRef.current?.click()}>
            {busy ? "Analyzing…" : "Upload floor plan"}
          </button>
          <button style={styles.ghostBtn} onClick={() => setView("edit")}>
            Verify &amp; edit
          </button>
          {source === "parsed" && (
            <button style={styles.ghostBtn} onClick={() => loadScene(coffeeBerryScene, "sample")}>
              Back to sample
            </button>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp"
          style={{ display: "none" }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.target.value = "";
          }}
        />
        <div style={styles.styleRow}>
          <span style={{ fontSize: 11, color: "#8a847a" }}>Style</span>
          <select value={style} onChange={(e) => changeStyle(e.target.value)} style={styles.select}>
            {Object.values(STYLE_PRESETS).map((p) => (
              <option key={p.key} value={p.key}>{p.name}</option>
            ))}
          </select>
          <button style={styles.aiBtn} disabled={styleBusy} onClick={aiDesign}>
            {styleBusy ? "Designing…" : "✨ AI design"}
          </button>
          <button style={styles.aiBtn} disabled={arrangeBusy} onClick={aiArrange} title="AI picks each fixture's facing + model and places WC fixtures">
            {arrangeBusy ? "Arranging…" : "🪑 AI arrange"}
          </button>
        </div>
        {designNote && <div style={styles.designNote}>{designNote}</div>}
        {error && <div style={styles.error}>⚠ {error}</div>}
        {meta && (
          <div style={styles.meta}>
            {meta.model} · {(meta.usage.input_tokens + meta.usage.output_tokens).toLocaleString()} tokens ·
            ~${meta.estCostUsd.toFixed(3)} · {(meta.elapsedMs / 1000).toFixed(1)}s
          </div>
        )}
      </div>

      {/* Mode toggle */}
      <div style={styles.topRight}>
        <button
          style={{ ...styles.modeBtn, ...(mode === "orbit" ? styles.modeBtnActive : {}) }}
          onClick={() => setMode("orbit")}
        >
          Orbit
        </button>
        <button
          style={{ ...styles.modeBtn, ...(mode === "walk" ? styles.modeBtnActive : {}) }}
          onClick={() => setMode("walk")}
          title="Walk through the café: numbered stops, guided tour, mini-map"
        >
          🚶 Walk tour
        </button>
      </div>

      {/* Controls hint */}
      <div style={styles.bottomLeft}>
        {mode === "orbit" ? (
          <span>Drag to orbit · scroll to zoom · click a fixture to inspect</span>
        ) : (
          <span>Click the scene to look · W A S D / arrows to walk · ESC to release</span>
        )}
      </div>

      {/* Render / export panel */}
      <div style={styles.renderPanel}>
        <button style={styles.rbtnAccent} onClick={() => setDesignPanel(true)} title="Claude designs the interior from the plan + references and writes a complete walkable 3D tour">🎨 AI design tour</button>
        <button style={styles.rbtn} onClick={dollhouse} title="Isometric dollhouse view (Reference B)">🏠 Dollhouse</button>
        <button style={styles.rbtn} onClick={downloadPng} title="Export the current view as a PNG">📸 Download PNG</button>
        <button style={styles.rbtnAccent} disabled={tourBusy || renderBusy} onClick={() => generateTour()} title="Build a walkable photoreal 360° tour in Blender">
          {tourBusy ? "Building tour…" : "🎬 Photoreal Tour"}
        </button>
        <button style={styles.rbtn} disabled={tourBusy || renderBusy} onClick={blenderRender} title="Single photoreal Blender Cycles render of the current view">
          {renderBusy ? "Rendering…" : "📷 Blender Still"}
        </button>
        <button style={styles.rbtn} disabled={tourBusy || renderBusy} onClick={aiPhotoreal} title="AI photoreal render (needs an image-model key)">
          ✨ AI Photoreal
        </button>
        {renderMsg && <div style={styles.renderMsg}>{renderMsg}</div>}
      </div>

      {designPanel && (
        <DesignTourPanel
          scene={scene}
          planImages={planImages}
          onClose={() => setDesignPanel(false)}
          onOpen={(u) => {
            setDesignPanel(false);
            setDesignUrl(u);
          }}
          onBlenderResult={(r) => {
            setDesignPanel(false);
            setBlenderResult(r);
          }}
        />
      )}

      {/* Building-tour overlay with live progress */}
      {tourBusy && (
        <div style={styles.tourBusy}>
          <div style={styles.tourBusyCard}>
            <div style={{ fontWeight: 700, fontSize: 15 }}>Building your photoreal 360° tour…</div>
            <div style={styles.progCount}>{Math.round(tourProgress?.percent ?? 0)}%</div>
            <div style={styles.progTrack}>
              <div style={{ ...styles.progFill, width: `${Math.max(3, tourProgress?.percent ?? 0)}%` }} />
            </div>
            <div style={{ fontSize: 12.5, color: "#c7bdac", marginTop: 10, minHeight: 16 }}>
              {tourProgress?.label ?? "Starting…"}
            </div>
            <div style={{ fontSize: 11.5, color: "#8f857a", marginTop: 6 }}>
              Rendering each room of {scene.project.name} in Blender.
            </div>
            <button style={styles.tourCancel} onClick={cancelTour}>Cancel</button>
          </div>
        </div>
      )}

      {/* Blender render result overlay */}
      {renderImg && (
        <div style={styles.renderOverlay} onClick={() => setRenderImg(null)}>
          <div style={styles.renderModal} onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={renderImg} alt="Blender Cycles render" style={styles.renderImage} />
            <div style={styles.renderModalBar}>
              <button style={styles.rbtn} onClick={() => downloadDataUrl(renderImg, `${scene.project.name.replace(/\W+/g, "_")}_blender.png`)}>📥 Download</button>
              <button style={styles.rbtn} onClick={() => setRenderImg(null)}>✕ Close</button>
            </div>
          </div>
        </div>
      )}

      {/* Issues panel */}
      {issues.length > 0 && (
        <div style={styles.issues}>
          <div style={styles.issuesHeader} onClick={() => setShowIssues((s) => !s)}>
            <span>
              {errCount > 0 && <b style={{ color: "#c0392b" }}>{errCount} errors </b>}
              {warnCount > 0 && <b style={{ color: "#b9770e" }}>{warnCount} warnings </b>}
              {errCount + warnCount === 0 && <span>{issues.length} notes </span>}
              (parser confidence)
            </span>
            <span>{showIssues ? "▾" : "▸"}</span>
          </div>
          {showIssues && (
            <div style={styles.issuesList}>
              {issues.slice(0, 40).map((i) => (
                <div key={i.id} style={styles.issueRow}>
                  <span style={{ ...styles.sev, ...sevStyle(i.severity) }}>{i.severity[0].toUpperCase()}</span>
                  <span>{i.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Inspector */}
      {selected && (
        <div style={styles.inspector}>
          <div style={styles.inspectorHeader}>
            <span>Fixture</span>
            <button style={styles.close} onClick={() => setSelected(null)}>
              ✕
            </button>
          </div>
          <div style={styles.inspName}>{selected.name}</div>
          <Row k="Category" v={selected.category} />
          {selected.legendNo && <Row k="Legend №" v={selected.legendNo} />}
          <Row k="Footprint" v={`${selected.footprint[0].toFixed(2)} × ${selected.footprint[1].toFixed(2)} m`} />
          <Row k="Height" v={`${(selected.height ?? 0).toFixed(2)} m`} />
          <Row k="Position" v={`(${selected.position[0].toFixed(2)}, ${selected.position[1].toFixed(2)})`} />
          <Row k="Placed by" v={selected.placedBy} />
          <Row k="Confidence" v={`${Math.round(selected.confidence * 100)}%`} />
        </div>
      )}

      {/* Busy overlay */}
      {busy && (
        <div style={styles.busy}>
          <div style={styles.busyCard}>
            <div style={styles.spinner} />
            <div style={{ fontWeight: 700, marginTop: 10 }}>Understanding your floor plan…</div>
            <div style={{ fontSize: 12, color: "#6b655c", marginTop: 4 }}>
              Claude is extracting walls, rooms, openings and equipment.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={styles.row}>
      <span style={styles.rowK}>{k}</span>
      <span style={styles.rowV}>{v}</span>
    </div>
  );
}

function sevStyle(sev: string): CSSProperties {
  if (sev === "error") return { background: "#c0392b" };
  if (sev === "warning") return { background: "#b9770e" };
  return { background: "#7a8a99" };
}

const styles: Record<string, CSSProperties> = {
  root: { position: "fixed", inset: 0, overflow: "hidden", background: "#e7e3da", fontFamily: "system-ui, sans-serif" },
  loading: { position: "absolute", inset: 0, display: "grid", placeItems: "center", color: "#555" },
  topLeft: { position: "absolute", top: 18, left: 18, padding: "12px 16px", background: "rgba(255,255,255,0.86)", backdropFilter: "blur(8px)", borderRadius: 12, boxShadow: "0 4px 20px rgba(0,0,0,0.12)", maxWidth: 380 },
  badge: { fontSize: 10, letterSpacing: 1.5, fontWeight: 700, color: "#9a6b2f" },
  title: { fontSize: 18, margin: "4px 0 2px", color: "#23201b" },
  sub: { fontSize: 12, color: "#6b655c" },
  actions: { display: "flex", gap: 8, marginTop: 10 },
  primaryBtn: { border: "none", background: "#23201b", color: "#fff", padding: "8px 14px", borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: "pointer" },
  ghostBtn: { border: "1px solid #cfc8bc", background: "transparent", color: "#4a453d", padding: "8px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer" },
  styleRow: { display: "flex", alignItems: "center", gap: 8, marginTop: 10 },
  select: { border: "1px solid #d6cfbf", borderRadius: 7, padding: "6px 8px", fontSize: 13, background: "#fff", color: "#2b2620", cursor: "pointer" },
  aiBtn: { border: "1px solid #9a6b2f", background: "#fff6ea", color: "#9a6b2f", padding: "6px 12px", borderRadius: 7, fontSize: 13, fontWeight: 600, cursor: "pointer" },
  designNote: { marginTop: 8, fontSize: 11.5, color: "#5b5349", background: "#f5efe3", padding: "7px 10px", borderRadius: 7, lineHeight: 1.4 },
  error: { marginTop: 10, fontSize: 12, color: "#c0392b", background: "#fbeceb", padding: "7px 10px", borderRadius: 7 },
  meta: { marginTop: 8, fontSize: 11, color: "#8a847a" },
  topRight: { position: "absolute", top: 18, right: 18, display: "flex", gap: 6, background: "rgba(255,255,255,0.86)", backdropFilter: "blur(8px)", borderRadius: 10, padding: 5, boxShadow: "0 4px 20px rgba(0,0,0,0.12)" },
  modeBtn: { border: "none", background: "transparent", padding: "7px 14px", borderRadius: 7, fontSize: 13, cursor: "pointer", color: "#4a453d", fontWeight: 600 },
  modeBtnActive: { background: "#23201b", color: "#fff" },
  bottomLeft: { position: "absolute", bottom: 18, left: 18, fontSize: 12, color: "#4a453d", background: "rgba(255,255,255,0.8)", padding: "7px 12px", borderRadius: 8 },
  renderPanel: { position: "absolute", bottom: 18, left: "50%", transform: "translateX(-50%)", display: "flex", flexWrap: "wrap", justifyContent: "center", gap: 8, maxWidth: 440, background: "rgba(255,255,255,0.9)", backdropFilter: "blur(8px)", borderRadius: 12, padding: 10, boxShadow: "0 4px 20px rgba(0,0,0,0.14)" },
  rbtn: { border: "1px solid #d6cfbf", background: "#faf8f3", padding: "8px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer", color: "#3a352e", fontWeight: 600 },
  rbtnAccent: { border: "1px solid #9a6b2f", background: "#fff6ea", color: "#9a6b2f", padding: "8px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600 },
  renderMsg: { flexBasis: "100%", fontSize: 11.5, color: "#5b5349", lineHeight: 1.4, textAlign: "center", marginTop: 2, whiteSpace: "pre-wrap" },
  renderOverlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.75)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, padding: 24 },
  renderModal: { background: "#1a1713", borderRadius: 12, overflow: "hidden", maxWidth: "92vw", maxHeight: "92vh", display: "flex", flexDirection: "column", boxShadow: "0 12px 48px rgba(0,0,0,0.5)" },
  renderImage: { maxWidth: "92vw", maxHeight: "80vh", display: "block", objectFit: "contain" },
  renderModalBar: { display: "flex", gap: 8, justifyContent: "flex-end", padding: 10, background: "#211d18" },
  tourBusy: { position: "fixed", inset: 0, background: "rgba(13,11,9,0.82)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1100, backdropFilter: "blur(3px)" },
  tourBusyCard: { textAlign: "center", color: "#f3ece0", padding: "26px 30px", background: "#1b1713", borderRadius: 16, border: "1px solid rgba(255,210,150,0.2)", boxShadow: "0 12px 48px rgba(0,0,0,0.5)", width: 340, maxWidth: "90vw" },
  progCount: { fontSize: 34, fontWeight: 800, color: "#ffce8f", margin: "10px 0 8px", fontVariantNumeric: "tabular-nums" },
  progTrack: { width: "100%", height: 8, borderRadius: 999, background: "rgba(255,255,255,0.1)", overflow: "hidden" },
  progFill: { height: "100%", borderRadius: 999, background: "linear-gradient(90deg,#ffb347,#ffce8f)", transition: "width 0.4s ease" },
  tourCancel: { marginTop: 18, background: "rgba(255,255,255,0.08)", color: "#e8e0d2", border: "1px solid rgba(255,255,255,0.18)", padding: "7px 18px", borderRadius: 8, fontSize: 13, cursor: "pointer", fontWeight: 600 },
  designBar: { position: "absolute", top: 12, left: 12, right: 12, display: "flex", alignItems: "center", gap: 8, pointerEvents: "none", zIndex: 5, flexWrap: "wrap" },
  gallery: { padding: "70px 24px 40px", display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(420px, 1fr))", gap: 18 },
  galleryItem: { margin: 0, background: "#1e1915", borderRadius: 12, overflow: "hidden", cursor: "zoom-in", boxShadow: "0 8px 30px rgba(0,0,0,0.4)" },
  galleryImg: { width: "100%", display: "block", aspectRatio: "16/9", objectFit: "cover" },
  galleryCap: { padding: "10px 12px", color: "#e8dfd0", fontSize: 13 },
  galleryNote: { gridColumn: "1 / -1", color: "#c7bdac", fontSize: 13, padding: 12 },
  designBadge: { background: "rgba(20,17,14,0.78)", color: "#ffd9a0", border: "1px solid rgba(255,210,150,0.25)", padding: "6px 12px", borderRadius: 999, fontSize: 13, fontWeight: 700, backdropFilter: "blur(8px)", pointerEvents: "auto" },
  designLink: { pointerEvents: "auto", background: "rgba(20,17,14,0.78)", color: "#f3ece0", border: "1px solid rgba(255,255,255,0.18)", padding: "6px 12px", borderRadius: 999, fontSize: 13, cursor: "pointer", textDecoration: "none", backdropFilter: "blur(8px)" },
  designExit: { marginLeft: "auto", pointerEvents: "auto", background: "rgba(20,17,14,0.78)", color: "#f3ece0", border: "1px solid rgba(255,255,255,0.18)", padding: "6px 12px", borderRadius: 8, fontSize: 13, cursor: "pointer", backdropFilter: "blur(8px)" },
  dnd: { position: "absolute", inset: 0, zIndex: 40, display: "grid", placeItems: "center", background: "rgba(154,107,47,0.14)", border: "3px dashed #9a6b2f", pointerEvents: "none" },
  dndCard: { background: "#fff", padding: "16px 24px", borderRadius: 12, fontWeight: 700, color: "#23201b", boxShadow: "0 8px 30px rgba(0,0,0,0.2)" },
  issues: { position: "absolute", bottom: 18, right: 18, width: 320, maxHeight: "45vh", overflow: "hidden", display: "flex", flexDirection: "column", background: "rgba(255,255,255,0.92)", backdropFilter: "blur(8px)", borderRadius: 12, boxShadow: "0 6px 26px rgba(0,0,0,0.16)" },
  issuesHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 12px", fontSize: 12, cursor: "pointer", borderBottom: "1px solid #eee" },
  issuesList: { overflowY: "auto", padding: "6px 10px" },
  issueRow: { display: "flex", gap: 8, alignItems: "flex-start", fontSize: 11.5, color: "#3a352e", padding: "4px 0" },
  sev: { color: "#fff", borderRadius: 4, fontSize: 9, fontWeight: 700, width: 15, height: 15, display: "inline-flex", alignItems: "center", justifyContent: "center", flex: "0 0 auto", marginTop: 1 },
  inspector: { position: "absolute", top: 18, right: 18, marginTop: 56, width: 260, background: "rgba(255,255,255,0.94)", backdropFilter: "blur(8px)", borderRadius: 12, padding: 14, boxShadow: "0 6px 26px rgba(0,0,0,0.16)" },
  inspectorHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 10, letterSpacing: 1.5, fontWeight: 700, color: "#9a6b2f" },
  close: { border: "none", background: "transparent", cursor: "pointer", fontSize: 13, color: "#888" },
  inspName: { fontSize: 15, fontWeight: 700, margin: "6px 0 10px", color: "#23201b" },
  row: { display: "flex", justifyContent: "space-between", fontSize: 12, padding: "3px 0", borderTop: "1px solid #eee" },
  rowK: { color: "#8a847a" },
  rowV: { color: "#2a2620", fontWeight: 600, textTransform: "capitalize" },
  busy: { position: "absolute", inset: 0, display: "grid", placeItems: "center", background: "rgba(231,227,218,0.55)", backdropFilter: "blur(2px)" },
  busyCard: { background: "#fff", borderRadius: 14, padding: "22px 30px", textAlign: "center", boxShadow: "0 10px 40px rgba(0,0,0,0.2)" },
  spinner: { width: 30, height: 30, margin: "0 auto", border: "3px solid #e3ddd1", borderTopColor: "#9a6b2f", borderRadius: "50%", animation: "cvspin 0.9s linear infinite" },
};
