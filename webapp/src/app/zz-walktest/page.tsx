"use client";

// Dev-only: open the web walkthrough of a saved Blender design directly, e.g. /zz-walktest?id=20261111-ca3978
// (used by scripts/walk-shots.mjs to screenshot the viewer headlessly).

import dynamic from "next/dynamic";
import { useSyncExternalStore } from "react";

const BlenderWalkViewer = dynamic(() => import("@/components/tour/BlenderWalkViewer"), { ssr: false });

export default function WalkTest() {
  const id = useSyncExternalStore(
    () => () => {},
    () => new URLSearchParams(window.location.search).get("id"),
    () => null,
  );
  if (!id) return <div style={{ padding: 24 }}>Pass ?id=&lt;design id&gt;</div>;
  const base = `/blender-designs/${id}`;
  return (
    <div style={{ position: "fixed", inset: 0 }}>
      <BlenderWalkViewer glbUrl={`${base}/cafe.glb`} sceneUrl={`${base}/scene.json`} projectName={id} />
    </div>
  );
}
