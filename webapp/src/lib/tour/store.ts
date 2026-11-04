// Mutable, frame-driven state for the walkable tour. No React in here: the R3F controller calls
// tick(dt) every frame and the overlay subscribes for the few things that need a re-render
// (current stop, card, toast, evening, map). Camera pose is read directly from `cam` each frame.

import type { TourModel, TourStop, XZ } from "./model";
import { EYE_HEIGHT, whereLabel } from "./model";

export interface Flight {
  pts: XZ[];
  lens: number[];
  total: number;
  t: number;
  dur: number;
  yaw0: number;
  pitch0: number;
  yaw1: number;
  pitch1: number;
  lastTravel: number;
  onDone?: () => void;
}

export interface Card {
  kicker: string;
  title: string;
  text: string;
}

const WALK_SPEED = 1.6; // m/s
const RUN_SPEED = 3.2;
const FLIGHT_SPEED = 1.7;
const STOP_DWELL = 5.5; // seconds the auto tour rests at each stop

const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
};
export function angDiff(a: number, b: number): number {
  let d = b - a;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return d;
}
/** yaw/pitch (three.js YXZ order) that looks from f to t. */
function lookAngles(fx: number, fy: number, fz: number, tx: number, ty: number, tz: number) {
  const dx = tx - fx, dz = tz - fz, dy = ty - fy;
  return { yaw: Math.atan2(-dx, -dz), pitch: Math.atan2(dy, Math.hypot(dx, dz)) };
}

export class TourStore {
  readonly model: TourModel;
  cam = { x: 0, z: 0, yaw: 0, pitch: 0, bob: 0 };
  fov = 68;
  keys: Record<string, boolean> = {};
  joy = { x: 0, y: 0 };
  flight: Flight | null = null;
  tourOn = false;
  private tourWait = 0;
  currentNode = -1;
  evening = false;
  mapVisible = true;
  help = true;
  card: Card | null = null;
  toastText = "";
  toastVisible = false;
  where = { prefix: "You’re", name: "outside" };
  reduceMotion = false;
  version = 0;
  private listeners = new Set<() => void>();
  private toastTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(model: TourModel) {
    this.model = model;
    if (typeof window !== "undefined") {
      this.reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
      this.mapVisible = window.innerWidth >= 480;
    }
    if (model.stops.length) this.setNodeImmediate(0);
    else {
      const b = model.bounds;
      this.cam.x = (b.minX + b.maxX) / 2;
      this.cam.z = (b.minZ + b.maxZ) / 2;
    }
    this.currentNode = -1;
    this.updateWhere();
  }

  /* ---------- subscription ---------- */
  subscribe = (fn: () => void) => {
    this.listeners.add(fn);
    return () => {
      this.listeners.delete(fn);
    };
  };
  emit() {
    this.version++;
    for (const fn of this.listeners) fn();
  }
  dispose() {
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.listeners.clear();
  }

  /* ---------- stops / flights ---------- */
  get stops(): TourStop[] {
    return this.model.stops;
  }

  setNodeImmediate(i: number) {
    const n = this.model.stops[i];
    if (!n) return;
    this.cam.x = n.pos[0];
    this.cam.z = n.pos[1];
    const a = lookAngles(this.cam.x, EYE_HEIGHT, this.cam.z, n.look[0], n.look[1], n.look[2]);
    this.cam.yaw = a.yaw;
    this.cam.pitch = a.pitch;
    this.currentNode = i;
  }

  private startFlight(pts: XZ[], look: [number, number, number] | null, onDone?: () => void, speed = FLIGHT_SPEED) {
    const lens = [0];
    for (let k = 1; k < pts.length; k++) lens.push(lens[k - 1] + Math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1]));
    const total = lens[lens.length - 1];
    const end = pts[pts.length - 1];
    let yaw1: number, pitch1: number;
    if (look) {
      const fa = lookAngles(end[0], EYE_HEIGHT, end[1], look[0], look[1], look[2]);
      yaw1 = fa.yaw;
      pitch1 = fa.pitch;
    } else {
      // keep heading: face the way we were walking
      const a = pts[Math.max(0, pts.length - 2)];
      yaw1 = total > 0.05 ? Math.atan2(-(end[0] - a[0]), -(end[1] - a[1])) : this.cam.yaw;
      pitch1 = 0;
    }
    const dur = Math.max(look ? 1.2 : 0.5, total / speed);
    this.flight = { pts, lens, total, t: 0, dur, yaw0: this.cam.yaw, pitch0: this.cam.pitch, yaw1, pitch1, lastTravel: this.cam.yaw, onDone };
  }

  goNode(i: number, fromTour = false) {
    const stop = this.model.stops[i];
    if (!stop) return;
    if (!fromTour) this.stopTour(false);
    this.card = null;
    this.currentNode = -1;
    const pts = this.model.nav.path([this.cam.x, this.cam.z], stop.pos);
    if (!pts) {
      // unreachable (no door found) — jump straight there
      this.setNodeImmediate(i);
      this.arrive(i);
      return;
    }
    this.startFlight(pts, stop.look, () => this.arrive(i));
    this.emit();
  }

  private arrive(i: number) {
    this.currentNode = i;
    this.showStory(i);
    if (this.tourOn) this.tourWait = this.reduceMotion ? 4.5 : STOP_DWELL;
    this.emit();
  }

  private stepFlight(dt: number) {
    const f = this.flight!;
    f.t += dt;
    const u = Math.min(1, f.t / f.dur);
    const s = ease(u) * f.total;
    let k = 1;
    while (k < f.lens.length - 1 && f.lens[k] < s) k++;
    const a = f.pts[k - 1], b = f.pts[k] ?? a;
    const seg = f.lens[k] - f.lens[k - 1] || 1;
    const w = Math.min(1, Math.max(0, (s - f.lens[k - 1]) / seg));
    const nx = a[0] + (b[0] - a[0]) * w, nz = a[1] + (b[1] - a[1]) * w;
    if (f.total > 0.6) {
      const ty = Math.atan2(-(b[0] - a[0]), -(b[1] - a[1]));
      f.lastTravel = f.lastTravel + angDiff(f.lastTravel, ty) * Math.min(1, dt * 4);
    }
    const startBlend = smooth(0, 0.12, u), endBlend = smooth(0.72, 1, u);
    const travelYaw = f.total > 0.6 ? f.lastTravel : f.yaw1;
    let y = f.yaw0 + angDiff(f.yaw0, travelYaw) * startBlend;
    y = y + angDiff(y, f.yaw1) * endBlend;
    this.cam.yaw = y;
    const midPitch = f.pitch0 + (-0.04 - f.pitch0) * startBlend;
    this.cam.pitch = midPitch + (f.pitch1 - midPitch) * endBlend;
    if (!this.reduceMotion) this.cam.bob += Math.hypot(nx - this.cam.x, nz - this.cam.z);
    this.cam.x = nx;
    this.cam.z = nz;
    if (u >= 1) {
      const done = f.onDone;
      this.flight = null;
      done?.();
    }
  }

  private tryMove(dx: number, dz: number): boolean {
    const nav = this.model.nav;
    let moved = false;
    if (nav.free(this.cam.x + dx, this.cam.z)) { this.cam.x += dx; moved = true; }
    if (nav.free(this.cam.x, this.cam.z + dz)) { this.cam.z += dz; moved = true; }
    if (moved && !this.reduceMotion) this.cam.bob += Math.hypot(dx, dz);
    return moved;
  }

  /** The user grabbed control: cancel any automated motion. */
  userMoved() {
    let changed = false;
    if (this.tourOn) { this.stopTour(false); changed = true; }
    if (this.flight) { this.flight = null; changed = true; }
    if (this.currentNode !== -1) { this.currentNode = -1; changed = true; }
    if (changed) this.emit();
  }

  /** Walk to a world point (click on floor / map). */
  walkTo(x: number, z: number) {
    const nav = this.model.nav;
    if (!nav.free(x, z)) {
      const alt = nav.nearestFree(x, z, undefined, 3);
      if (!alt || Math.hypot(alt[0] - x, alt[1] - z) > 0.6) { this.toast("That spot is blocked"); return; }
      x = alt[0]; z = alt[1];
    }
    const pts = nav.path([this.cam.x, this.cam.z], [x, z]);
    if (!pts) { this.toast("No way through to there"); return; }
    this.stopTour(false);
    this.card = null;
    this.currentNode = -1;
    this.startFlight(pts, null, undefined, FLIGHT_SPEED);
    this.emit();
  }

  /** Click on something in the 3D view. */
  clickWorld(x: number, y: number, z: number, isFloor: boolean, normalY: number) {
    if (!isFloor && normalY < 0.7) { this.toast("Click the floor to walk there"); return; }
    if (!isFloor && y > 0.15) { this.toast("Click the floor to walk there"); return; }
    if (Math.hypot(x - this.cam.x, z - this.cam.z) > 18) { this.toast("Too far, walk closer first"); return; }
    this.walkTo(x, z);
  }

  /* ---------- auto tour ---------- */
  startTour() {
    if (!this.model.stops.length) return;
    this.tourOn = true;
    this.help = false;
    const start = this.currentNode >= 0 && this.currentNode < this.model.stops.length - 1 ? this.currentNode + 1 : 0;
    this.goNode(start, true);
    this.emit();
  }
  stopTour(emit = true) {
    this.tourOn = false;
    this.tourWait = 0;
    if (emit) this.emit();
  }
  toggleTour() {
    if (this.tourOn) this.stopTour();
    else this.startTour();
  }

  /* ---------- UI bits ---------- */
  showStory(i: number) {
    const n = this.model.stops[i];
    if (!n) return;
    this.card = { kicker: `Stop ${i + 1} of ${this.model.stops.length}`, title: n.title, text: n.text };
    this.emit();
  }
  showHotspot(id: string) {
    const h = this.model.hotspots.find((x) => x.id === id);
    if (!h) return;
    this.card = { kicker: "Detail", title: h.title, text: h.text };
    this.emit();
  }
  hideCard() {
    if (!this.card) return;
    this.card = null;
    this.emit();
  }
  toast(text: string) {
    this.toastText = text;
    this.toastVisible = true;
    if (this.toastTimer) clearTimeout(this.toastTimer);
    this.toastTimer = setTimeout(() => {
      this.toastTimer = null;
      this.toastVisible = false;
      this.emit();
    }, 1400);
    this.emit();
  }
  /** Input plumbing (kept as methods so React handlers never mutate the store directly). */
  setJoy(x: number, y: number) {
    this.joy.x = x;
    this.joy.y = y;
  }
  setKey(code: string, down: boolean) {
    this.keys[code] = down;
  }
  clearKeys() {
    for (const k in this.keys) this.keys[k] = false;
  }
  /** Mouse / touch look. */
  look(dx: number, dy: number) {
    this.cam.yaw += dx;
    this.cam.pitch = Math.max(-1.2, Math.min(1.2, this.cam.pitch + dy));
  }
  setEvening(v: boolean) {
    if (this.evening === v) return;
    this.evening = v;
    this.emit();
  }
  toggleMap() {
    this.mapVisible = !this.mapVisible;
    this.emit();
  }
  setHelp(v: boolean) {
    if (this.help === v) return;
    this.help = v;
    this.emit();
  }
  setFov(f: number) {
    this.fov = Math.max(40, Math.min(80, f));
  }

  private updateWhere() {
    const w = whereLabel(this.model.nav, this.cam.x, this.cam.z);
    if (w.name !== this.where.name) {
      this.where = w;
      this.emit();
    }
  }

  /* ---------- per-frame ---------- */
  tick(dt: number) {
    const k = this.keys;
    const fwd = (k.KeyW || k.ArrowUp ? 1 : 0) - (k.KeyS || k.ArrowDown ? 1 : 0) + -this.joy.y;
    const str = (k.KeyD ? 1 : 0) - (k.KeyA ? 1 : 0) + this.joy.x;
    const turn = (k.ArrowLeft ? 1 : 0) - (k.ArrowRight ? 1 : 0) + (k.KeyQ ? 1 : 0) - (k.KeyE ? 1 : 0);
    if (Math.abs(fwd) > 0.05 || Math.abs(str) > 0.05 || Math.abs(turn) > 0.05) {
      if (this.flight || this.tourOn) this.userMoved();
      this.cam.yaw += turn * dt * 1.6;
      const sp = (k.ShiftLeft || k.ShiftRight ? RUN_SPEED : WALK_SPEED) * dt;
      const sx = -Math.sin(this.cam.yaw), sz = -Math.cos(this.cam.yaw);
      const rx = Math.cos(this.cam.yaw), rz = -Math.sin(this.cam.yaw);
      let mx = sx * fwd + rx * str, mz = sz * fwd + rz * str;
      const l = Math.hypot(mx, mz);
      if (l > 1) { mx /= l; mz /= l; }
      if (l > 0.02) {
        this.tryMove(mx * sp, mz * sp);
        if (this.currentNode !== -1) { this.currentNode = -1; this.emit(); }
      }
    }
    if (this.flight) this.stepFlight(dt);
    if (this.tourOn && !this.flight && this.tourWait > 0) {
      this.tourWait -= dt;
      if (this.tourWait <= 0) {
        const nx = this.currentNode + 1;
        if (nx < this.model.stops.length) this.goNode(nx, true);
        else { this.stopTour(); this.toast("Tour complete"); }
      }
    }
    this.updateWhere();
  }
}
