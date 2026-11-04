"use client";

// First-person walk controller for the live three.js café (reference: the hand-built
// "Walkable virtual tour" page). Drag to look, W A S D / arrows to walk, click the floor to walk
// there, click a "+" marker for a detail card. All motion state lives in the TourStore; this
// component only pumps it each frame and drives a camera it owns.

import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";
import type { TourStore } from "@/lib/tour/store";
import { EYE_HEIGHT } from "@/lib/tour/model";

function makeHotTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d")!;
  g.beginPath();
  g.arc(64, 64, 52, 0, Math.PI * 2);
  g.fillStyle = "rgba(32,22,15,.55)";
  g.fill();
  g.lineWidth = 7;
  g.strokeStyle = "#d9ab72";
  g.stroke();
  g.fillStyle = "#f5ead9";
  g.fillRect(60, 38, 8, 52);
  g.fillRect(38, 60, 52, 8);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function makeSky(evening: boolean): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = 16;
  c.height = 256;
  const g = c.getContext("2d")!;
  const lg = g.createLinearGradient(0, 0, 0, 256);
  if (evening) {
    lg.addColorStop(0, "#2a3657");
    lg.addColorStop(0.5, "#8e6f86");
    lg.addColorStop(0.8, "#e7a173");
    lg.addColorStop(1, "#f4c58f");
  } else {
    lg.addColorStop(0, "#7fb1db");
    lg.addColorStop(0.55, "#c4dbea");
    lg.addColorStop(1, "#eef1ee");
  }
  g.fillStyle = lg;
  g.fillRect(0, 0, 16, 256);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

/** Scene-level look for the walk (sky background, no fog, neutral exposure). Returns a restore fn. */
function applyEnvironment(scene: THREE.Scene, gl: THREE.WebGLRenderer, store: TourStore, skies: { day: THREE.Texture; eve: THREE.Texture }) {
  const prev = { bg: scene.background, fog: scene.fog, exp: gl.toneMappingExposure };
  let applied: boolean | null = null;
  const apply = () => {
    if (applied === store.evening) return;
    applied = store.evening;
    scene.background = store.evening ? skies.eve : skies.day;
    scene.fog = null;
    gl.toneMappingExposure = store.evening ? 0.95 : 1.0;
  };
  apply();
  const unsub = store.subscribe(apply);
  return () => {
    unsub();
    scene.background = prev.bg;
    scene.fog = prev.fog;
    gl.toneMappingExposure = prev.exp;
  };
}

/** Make the canvas focusable and non-scrolling for the walk; returns a restore fn. */
function prepareCanvas(el: HTMLCanvasElement) {
  const prev = { touch: el.style.touchAction, cursor: el.style.cursor, tab: el.tabIndex };
  el.style.touchAction = "none";
  el.style.cursor = "grab";
  el.tabIndex = 0;
  return () => {
    el.style.touchAction = prev.touch;
    el.style.cursor = prev.cursor;
    el.tabIndex = prev.tab;
  };
}
function setCursor(el: HTMLCanvasElement, c: string) {
  el.style.cursor = c;
}

export default function WalkController({ store }: { store: TourStore }) {
  const camRef = useRef<THREE.PerspectiveCamera>(null);
  const hotGroup = useRef<THREE.Group>(null);
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const hotTex = useMemo(() => makeHotTexture(), []);
  const skies = useMemo(() => ({ day: makeSky(false), eve: makeSky(true) }), []);
  const ray = useMemo(() => new THREE.Raycaster(), []);
  const ndc = useMemo(() => new THREE.Vector2(), []);
  const tmpN = useMemo(() => new THREE.Vector3(), []);

  // Sky + exposure follow the store's day/evening flag; the orbit view's look is restored on exit.
  useEffect(() => applyEnvironment(scene, gl, store, skies), [scene, gl, store, skies]);

  useEffect(() => {
    const c = camRef.current;
    if (c) c.rotation.order = "YXZ";
  }, []);

  // Pointer: drag to look, click to walk / open details. Keyboard: walk keys.
  useEffect(() => {
    const el = gl.domElement;
    const restoreCanvas = prepareCanvas(el);
    let drag: { id: number; x: number; y: number; sx: number; sy: number; t: number; moved: boolean } | null = null;

    const clickAt = (cx: number, cy: number) => {
      const cam = camRef.current;
      if (!cam) return;
      const r = el.getBoundingClientRect();
      ndc.set(((cx - r.left) / r.width) * 2 - 1, -((cy - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(ndc, cam);
      const hg = hotGroup.current;
      if (hg) {
        const hh = ray.intersectObjects(hg.children, false);
        if (hh.length) {
          store.showHotspot(String(hh[0].object.userData.hotspotId));
          return;
        }
      }
      const hits = ray.intersectObjects(scene.children, true).filter((i) => {
        const o = i.object as THREE.Mesh & { isSprite?: boolean };
        if (o.isSprite) return false;
        const m = o.material as THREE.Material | THREE.Material[] | undefined;
        const mat = Array.isArray(m) ? m[0] : m;
        // invisible hit-boxes and glass don't count
        if (mat && mat.transparent && (mat as THREE.MeshStandardMaterial).opacity <= 0.3) return false;
        return true;
      });
      if (!hits.length) return;
      const h = hits[0];
      let ny = 1;
      if (h.face) {
        tmpN.copy(h.face.normal).transformDirection(h.object.matrixWorld);
        ny = tmpN.y;
      }
      store.clickWorld(h.point.x, h.point.y, h.point.z, h.object.userData.floor === true, ny);
    };

    const onDown = (e: PointerEvent) => {
      if (e.button !== 0 && e.pointerType === "mouse") return;
      el.focus({ preventScroll: true });
      drag = { id: e.pointerId, x: e.clientX, y: e.clientY, sx: e.clientX, sy: e.clientY, t: performance.now(), moved: false };
      try {
        el.setPointerCapture(e.pointerId);
      } catch {
        /* ignore */
      }
    };
    const onMove = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX;
      drag.y = e.clientY;
      if (!drag.moved && Math.hypot(e.clientX - drag.sx, e.clientY - drag.sy) > 5) {
        drag.moved = true;
        setCursor(el, "grabbing");
        store.userMoved();
      }
      if (drag.moved) {
        const k = e.pointerType === "touch" ? 0.006 : 0.0042;
        store.look(dx * k, dy * k * 0.85);
      }
    };
    const onUp = (e: PointerEvent) => {
      if (!drag || e.pointerId !== drag.id) return;
      const wasClick = !drag.moved && performance.now() - drag.t < 450;
      setCursor(el, "grab");
      drag = null;
      if (wasClick) clickAt(e.clientX, e.clientY);
    };
    const onCancel = () => {
      drag = null;
      setCursor(el, "grab");
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      store.setFov(store.fov + e.deltaY * 0.03);
    };
    const key = (down: boolean) => (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const tag = t?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (tag === "BUTTON" && (e.code === "Space" || e.code === "Enter")) return;
      store.setKey(e.code, down);
      if (down && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"].includes(e.code)) e.preventDefault();
      if (down && e.code === "Escape") {
        store.setHelp(false);
        store.hideCard();
      }
    };
    const onKeyDown = key(true);
    const onKeyUp = key(false);
    const onBlur = () => store.clearKeys();

    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointermove", onMove);
    el.addEventListener("pointerup", onUp);
    el.addEventListener("pointercancel", onCancel);
    el.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    window.addEventListener("blur", onBlur);
    return () => {
      restoreCanvas();
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointermove", onMove);
      el.removeEventListener("pointerup", onUp);
      el.removeEventListener("pointercancel", onCancel);
      el.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
      window.removeEventListener("blur", onBlur);
    };
  }, [gl, scene, store, ray, ndc, tmpN]);

  useFrame((_, dt) => {
    store.tick(Math.min(dt, 0.05));
    const c = camRef.current;
    if (!c) return;
    const bob = store.reduceMotion ? 0 : Math.sin((store.cam.bob * Math.PI * 2) / 1.3) * 0.018;
    c.position.set(store.cam.x, EYE_HEIGHT + bob, store.cam.z);
    c.rotation.set(store.cam.pitch, store.cam.yaw, 0);
    if (Math.abs(c.fov - store.fov) > 1e-3) {
      c.fov = store.fov;
      c.updateProjectionMatrix();
    }
    const g = hotGroup.current;
    if (g && !store.reduceMotion) {
      const s = 0.22 + Math.sin(performance.now() / 450) * 0.02;
      for (const h of g.children) h.scale.set(s, s, s);
    }
  });

  return (
    <>
      <PerspectiveCamera ref={camRef} makeDefault fov={68} near={0.05} far={300} position={[store.cam.x, EYE_HEIGHT, store.cam.z]} />
      <group ref={hotGroup}>
        {store.model.hotspots.map((h) => (
          <sprite key={h.id} position={h.pos} scale={[0.22, 0.22, 0.22]} renderOrder={5} userData={{ hotspotId: h.id }}>
            <spriteMaterial map={hotTex} transparent depthWrite={false} />
          </sprite>
        ))}
      </group>
    </>
  );
}
