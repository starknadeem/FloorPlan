// Shape the vision model returns (System 1's raw output), before normalization to CafeScene.
// Points are {x,y} objects (clearer for the model than tuples). Openings reference walls by index.

export interface PPoint {
  x: number;
  y: number;
}

export interface ParsedProject {
  name: string;
  drawnScale?: string;
  datumDescription: string;
  confidenceOverall: number;
}

export interface ParsedLegendItem {
  no: string;
  name: string;
  category: string;
}

export interface ParsedWall {
  a: PPoint;
  b: PPoint;
  thickness: number;
  height: number;
  exterior: boolean;
  confidence: number;
}

export interface ParsedOpening {
  type: string; // door | window | opening
  wallIndex: number;
  offset: number;
  width: number;
  height: number;
  sillHeight?: number;
  confidence: number;
}

export interface ParsedRoom {
  name: string;
  category: string;
  polygon: PPoint[];
  ceilingHeight: number;
  confidence: number;
}

export interface ParsedFixture {
  legendNo?: string;
  name: string;
  category: string;
  position: PPoint;
  rotation: number;
  footprint: { w: number; d: number };
  height?: number;
  baseHeight?: number;
  confidence: number;
}

export interface ParsedIssue {
  severity: "info" | "warning" | "error";
  message: string;
}

export interface ParsedPlan {
  project: ParsedProject;
  legend: ParsedLegendItem[];
  walls: ParsedWall[];
  openings: ParsedOpening[];
  rooms: ParsedRoom[];
  fixtures: ParsedFixture[];
  issues: ParsedIssue[];
}

// Enum value lists (also embedded in the prompt and used to coerce unknown values).
export const FIXTURE_CATEGORIES = [
  "counter",
  "espresso_machine",
  "grinder",
  "display_case",
  "cooling_case",
  "fridge",
  "freezer",
  "ice_maker",
  "sink",
  "dishwasher",
  "oven",
  "boiler",
  "blender",
  "mixer",
  "monitor",
  "table",
  "chair",
  "stool",
  "sofa",
  "banquette",
  "shelving",
  "menu_board",
  "signage",
  "plant",
  "pendant_light",
  "umbrella",
  "cashier",
  "generic",
] as const;

export const ROOM_CATEGORIES = [
  "seating_indoor",
  "seating_outdoor",
  "service_counter",
  "preparation",
  "kitchen",
  "storage",
  "wc",
  "wc_disabled",
  "corridor",
  "entrance",
  "other",
] as const;

export const OPENING_TYPES = ["door", "window", "opening"] as const;
