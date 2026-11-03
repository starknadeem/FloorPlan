// Phase 2.1 — deterministic geometry regularization ("dimension-graph lite").
//
// Architectural plans are overwhelmingly axis-aligned. The vision parser emits coordinates that are
// close but not perfectly consistent (walls a few cm off-axis, corners that nearly meet, collinear
// walls at slightly different coordinates). This pass enforces the consistency a dimension graph
// would: it clusters near-equal X and near-equal Y coordinates and snaps them to a shared value, so
// collinear walls align, corners weld, and right angles become exact — without touching angled walls
// whose coordinates form their own clusters.
//
// A full OpenCV + dimension-OCR + least-squares solver is a later increment; this is the robust,
// dependency-free first step.

import type { CafeScene, Vec2 } from "@/types/cafescene";

/** Build a snapping function from a set of 1-D values: near-equal values collapse to their mean. */
function axisSnapper(values: number[], tol: number): (x: number) => number {
  const sorted = [...values].sort((a, b) => a - b);
  const reps: number[] = [];
  let group: number[] = [];
  const flush = () => {
    if (group.length) reps.push(group.reduce((s, x) => s + x, 0) / group.length);
    group = [];
  };
  for (const v of sorted) {
    if (group.length && v - group[group.length - 1] > tol) flush();
    group.push(v);
  }
  flush();
  return (x: number) => {
    let best = x;
    let bd = tol + 1e-9;
    for (const r of reps) {
      const d = Math.abs(x - r);
      if (d <= tol && d < bd) {
        bd = d;
        best = r;
      }
    }
    return best;
  };
}

export interface RegularizeOptions {
  /** coordinate clustering tolerance in meters (default 0.25) */
  tol?: number;
}

/** Return a new scene with wall + room coordinates regularized (snapped to shared axes). */
export function regularizeScene(scene: CafeScene, opts: RegularizeOptions = {}): CafeScene {
  const tol = opts.tol ?? 0.25;

  const xs: number[] = [];
  const ys: number[] = [];
  for (const w of scene.walls) {
    xs.push(w.a[0], w.b[0]);
    ys.push(w.a[1], w.b[1]);
  }
  if (xs.length === 0) return scene;

  const snapX = axisSnapper(xs, tol);
  const snapY = axisSnapper(ys, tol);
  const sp = (p: Vec2): Vec2 => [snapX(p[0]), snapY(p[1])];

  const walls = scene.walls.map((w) => ({ ...w, a: sp(w.a), b: sp(w.b) }));
  const rooms = scene.rooms.map((r) => ({ ...r, polygon: r.polygon.map(sp) }));

  return { ...scene, walls, rooms };
}

/** Uniformly scale the plan's horizontal dimensions by factor k (heights are unchanged). */
export function scaleScene(scene: CafeScene, k: number): CafeScene {
  if (!isFinite(k) || k <= 0) return scene;
  const s2 = (p: Vec2): Vec2 => [p[0] * k, p[1] * k];
  return {
    ...scene,
    walls: scene.walls.map((w) => ({ ...w, a: s2(w.a), b: s2(w.b), thickness: w.thickness * k })),
    rooms: scene.rooms.map((r) => ({ ...r, polygon: r.polygon.map(s2) })),
    openings: scene.openings.map((o) => ({ ...o, offset: o.offset * k, width: o.width * k })),
    fixtures: scene.fixtures.map((f) => ({
      ...f,
      position: s2(f.position),
      footprint: [f.footprint[0] * k, f.footprint[1] * k] as Vec2,
    })),
  };
}
