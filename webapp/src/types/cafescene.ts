// CaféScene — canonical TypeScript types (schema v1.0)
// This mirrors CAFESCENE_SCHEMA.md. It is the single data contract between the three systems.
// Phase 1 only consumes it (the 3D Rendering Engine). Phases 2+ will produce it.

export type Vec2 = [number, number]; // meters, PLAN space (x right, y up-the-page)
export type Vec3 = [number, number, number]; // meters, WORLD space (y up) — System 3 only
export type Hex = string; // "#rrggbb"

export type SystemId = 1 | 2 | 3;

export interface Provenance {
  system: SystemId;
  method: "vision" | "cv" | "reconstruction" | "design" | "manual_edit" | "default";
  pageId?: string;
  note?: string;
}

export type OpeningType = "door" | "window" | "opening";
export type DoorSwing =
  | "none"
  | "left_in"
  | "left_out"
  | "right_in"
  | "right_out"
  | "double"
  | "sliding";

export type RoomCategory =
  | "seating_indoor"
  | "seating_outdoor"
  | "service_counter"
  | "preparation"
  | "kitchen"
  | "storage"
  | "wc"
  | "wc_disabled"
  | "corridor"
  | "entrance"
  | "other";

export type FixtureCategory =
  | "counter"
  | "espresso_machine"
  | "grinder"
  | "display_case"
  | "cooling_case"
  | "fridge"
  | "freezer"
  | "ice_maker"
  | "sink"
  | "dishwasher"
  | "oven"
  | "boiler"
  | "blender"
  | "mixer"
  | "monitor"
  | "table"
  | "chair"
  | "stool"
  | "sofa"
  | "banquette"
  | "shelving"
  | "menu_board"
  | "signage"
  | "plant"
  | "pendant_light"
  | "umbrella"
  | "cashier"
  | "generic";

export type SurfaceRole =
  | "floor"
  | "wall"
  | "ceiling"
  | "counter_front"
  | "counter_top"
  | "trim";

export type LightType =
  | "ambient"
  | "point"
  | "spot"
  | "area"
  | "pendant"
  | "daylight";

export type RenderType = "walkable_snapshot" | "photoreal" | "isometric";

export interface Project {
  id: string;
  name: string;
  units: "m";
  datum: { description: string; planOrigin: Vec2 };
  drawnScale?: string;
  confidenceOverall: number;
  createdAt: string;
  schemaVersion: "1.0";
}

export interface Page {
  id: string;
  role:
    | "floor_plan"
    | "section"
    | "elevation"
    | "ceiling_plan"
    | "legend"
    | "detail"
    | "other";
  sourceFile: string;
  language?: string;
}

export interface LegendItem {
  id: string;
  no: string;
  name: string;
  category: FixtureCategory;
  source: Provenance;
}

export interface Wall {
  id: string;
  a: Vec2;
  b: Vec2;
  thickness: number;
  height: number;
  baseHeight?: number;
  exterior?: boolean;
  materialRole?: SurfaceRole;
  confidence: number;
  source: Provenance;
}

export interface Opening {
  id: string;
  type: OpeningType;
  wallId: string;
  offset: number; // along centerline from wall.a to the opening's near edge
  width: number;
  height: number;
  sillHeight?: number; // windows
  swing?: DoorSwing;
  confidence: number;
  source: Provenance;
}

export interface Room {
  id: string;
  name: string;
  category: RoomCategory;
  polygon: Vec2[];
  ceilingHeight: number; // 0 => no ceiling (e.g. outdoor)
  floorMaterialId?: string;
  confidence: number;
  source: Provenance;
}

export interface Fixture {
  id: string;
  legendNo?: string;
  name: string;
  category: FixtureCategory;
  roomId?: string;
  position: Vec2; // footprint center, plan space
  rotation: number; // degrees CCW, 0 => local +Y faces plan +Y
  footprint: Vec2; // [width(x), depth(y)] at 0 degrees
  height?: number;
  baseHeight?: number; // off floor, default 0
  assetId?: string;
  placedBy: "parse" | "design";
  confidence: number;
  source: Provenance;
}

export interface AssetChoice {
  assetId: string;
  catalogKey: string;
  category: FixtureCategory;
  url: string;
  defaultDims?: Vec2;
}

export interface MaterialDef {
  id: string;
  role?: SurfaceRole;
  preset?: string;
  baseColor?: Hex;
  roughness?: number;
  metalness?: number;
  textureUrl?: string;
  specOrigin?: string;
}

export interface DesignSpec {
  style: string;
  palette: { name: string; hex: Hex }[];
  surfaceMaterials: Partial<Record<SurfaceRole, string>>;
  mood: { colorTempK: number; brightness: number; notes?: string };
  decorNotes?: string;
  assets: AssetChoice[];
  source: Provenance;
}

export interface LightSource {
  id: string;
  type: LightType;
  position?: Vec2;
  mountHeight?: number;
  intensity: number;
  colorTempK: number;
  source: Provenance;
}

export interface CameraPose {
  id?: string;
  position: Vec3;
  lookAt: Vec3;
  fovDeg?: number;
}

export interface RenderOutput {
  id: string;
  type: RenderType;
  imageUrl: string;
  camera: CameraPose;
  conditionedOn?: ("depth" | "normal" | "edge" | "segmentation")[];
  createdAt: string;
}

export interface SceneAssets {
  glbUrl?: string;
  renders: RenderOutput[];
}

export interface Issue {
  id: string;
  severity: "info" | "warning" | "error";
  message: string;
  elementId?: string;
  raisedBy: SystemId;
}

export interface CafeScene {
  schemaVersion: "1.0";
  project: Project;
  pages: Page[];
  legend: LegendItem[];
  walls: Wall[];
  openings: Opening[];
  rooms: Room[];
  fixtures: Fixture[];
  design?: DesignSpec;
  lights?: LightSource[];
  materials?: MaterialDef[];
  assets?: SceneAssets;
  issues?: Issue[];
}
