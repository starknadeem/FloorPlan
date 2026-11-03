// CafeScene validator — checks the invariants from CAFESCENE_SCHEMA.md §3.
// It never throws; it returns a list of Issues so an imperfect scene still renders
// (the verify editor in Phase 3 will surface these to the user).

import type { CafeScene, Issue } from "@/types/cafescene";
import { wallLength } from "@/lib/geometry";

export function validateScene(scene: CafeScene): Issue[] {
  const issues: Issue[] = [];
  let n = 0;
  const add = (severity: Issue["severity"], message: string, elementId?: string) =>
    issues.push({ id: `val_${++n}`, severity, message, elementId, raisedBy: 1 });

  // unique ids
  const ids = new Set<string>();
  const dup = new Set<string>();
  for (const e of [...scene.walls, ...scene.openings, ...scene.rooms, ...scene.fixtures]) {
    if (ids.has(e.id)) dup.add(e.id);
    ids.add(e.id);
  }
  if (dup.size) add("error", `Duplicate element ids: ${[...dup].join(", ")}`);

  // openings resolve + fit on their wall
  const wallById = new Map(scene.walls.map((w) => [w.id, w]));
  for (const op of scene.openings) {
    const w = wallById.get(op.wallId);
    if (!w) {
      add("error", `Opening ${op.id} references missing wall ${op.wallId}`, op.id);
      continue;
    }
    const L = wallLength(w.a, w.b);
    if (op.offset < -0.01 || op.offset + op.width > L + 0.05) {
      add("warning", `Opening ${op.id} (${op.offset.toFixed(2)}–${(op.offset + op.width).toFixed(2)}m) does not fit wall ${w.id} (length ${L.toFixed(2)}m)`, op.id);
    }
  }

  // rooms have >=3 points
  for (const r of scene.rooms) {
    if (r.polygon.length < 3) add("error", `Room ${r.id} has fewer than 3 polygon points`, r.id);
    if (r.ceilingHeight < 0) add("warning", `Room ${r.id} has negative ceiling height`, r.id);
  }

  // fixtures reference a legend number that exists (if set)
  const legendNos = new Set(scene.legend.map((l) => l.no));
  for (const f of scene.fixtures) {
    if (f.legendNo && !legendNos.has(f.legendNo)) {
      add("info", `Fixture ${f.id} references legend № ${f.legendNo} not found in legend`, f.id);
    }
    if (f.footprint[0] <= 0 || f.footprint[1] <= 0) {
      add("warning", `Fixture ${f.id} has a non-positive footprint`, f.id);
    }
  }

  // stage completeness
  if (scene.walls.length === 0) add("error", "Scene has no walls");
  if (scene.rooms.length === 0) add("warning", "Scene has no rooms");

  return issues;
}
