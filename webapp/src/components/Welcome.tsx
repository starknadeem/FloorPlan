"use client";

import { useRef, useState, type CSSProperties } from "react";

export default function Welcome({
  onPickFile,
  onSampleCafe,
  onParsedSample,
  onClose,
  error,
}: {
  onPickFile: (f: File) => void;
  onSampleCafe: () => void;
  onParsedSample: () => void;
  onClose: () => void;
  error: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);

  return (
    <div style={S.backdrop}>
      <div style={S.card}>
        <div style={S.badge}>CAFÉVISION · AI 2D → 3D</div>
        <h1 style={S.h1}>Turn a floor plan into a walkable 3D café</h1>
        <p style={S.sub}>
          Upload a 2D coffee-shop plan. The AI reads the walls, rooms, doors and equipment, builds an
          interactive 3D space, designs the interior, and lets you walk through it.
        </p>

        <div
          style={{ ...S.drop, ...(drag ? S.dropActive : {}) }}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDrag(true);
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDrag(false);
            const f = e.dataTransfer.files?.[0];
            if (f) onPickFile(f);
          }}
        >
          <div style={{ fontSize: 30 }}>⬆️</div>
          <div style={{ fontWeight: 700, marginTop: 6 }}>Upload a floor plan</div>
          <div style={{ fontSize: 12, color: "#8a847a", marginTop: 2 }}>
            Drag &amp; drop or click · PNG / JPG / WEBP
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            style={{ display: "none" }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onPickFile(f);
              e.target.value = "";
            }}
          />
        </div>

        {error && <div style={S.error}>⚠ {error}</div>}

        <div style={S.or}>or try a ready example</div>
        <div style={S.samples}>
          <button style={S.sample} onClick={onParsedSample}>
            <b>Real parsed plan</b>
            <span>The Coffee Berry plan, already AI-parsed — instant</span>
          </button>
          <button style={S.sample} onClick={onSampleCafe}>
            <b>Sample café</b>
            <span>A hand-crafted furnished café to explore</span>
          </button>
        </div>

        <button style={S.skip} onClick={onClose}>
          Skip →
        </button>
      </div>
    </div>
  );
}

const S: Record<string, CSSProperties> = {
  backdrop: { position: "absolute", inset: 0, display: "grid", placeItems: "center", background: "rgba(231,227,218,0.72)", backdropFilter: "blur(6px)", zIndex: 50, padding: 16 },
  card: { position: "relative", width: "min(560px, 94vw)", background: "#fff", borderRadius: 18, padding: "30px 32px", boxShadow: "0 20px 60px rgba(0,0,0,0.22)", textAlign: "center" },
  badge: { fontSize: 11, letterSpacing: 2, fontWeight: 700, color: "#9a6b2f" },
  h1: { fontSize: 25, margin: "10px 0 8px", color: "#23201b", lineHeight: 1.2 },
  sub: { fontSize: 13.5, color: "#6b655c", lineHeight: 1.5, maxWidth: 460, margin: "0 auto 18px" },
  drop: { border: "2px dashed #ccbfa6", borderRadius: 14, padding: "26px 16px", cursor: "pointer", background: "#faf7f0", transition: "all .15s" },
  dropActive: { borderColor: "#9a6b2f", background: "#f3e8d6" },
  error: { marginTop: 12, fontSize: 12.5, color: "#c0392b", background: "#fbeceb", padding: "8px 12px", borderRadius: 8, textAlign: "left" },
  or: { fontSize: 11.5, color: "#a69f93", textTransform: "uppercase", letterSpacing: 1, margin: "18px 0 10px" },
  samples: { display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" },
  sample: { flex: "1 1 200px", textAlign: "left", border: "1px solid #e2dccf", borderRadius: 12, padding: "12px 14px", cursor: "pointer", background: "#fff", display: "flex", flexDirection: "column", gap: 3, color: "#2a2620", fontSize: 13 },
  skip: { marginTop: 18, border: "none", background: "transparent", color: "#8a847a", fontSize: 13, cursor: "pointer" },
};
