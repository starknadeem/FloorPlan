// Design directions: genuinely different interior languages. Each AI run gets one (never one used
// recently), so the same floor plan produces a different café every time. Pure data, safe on the client.

export interface DesignDirection {
  id: string;
  name: string;
  /** cafe_kit style tag: selects which furniture/equipment variants may appear. */
  style: string;
  mood: "day" | "golden" | "evening";
  summary: string;
  /** Prose handed to the designer: palette, materials and signature moves. */
  spec: string;
}

/** The client's own shop standard (Coffee Berry): what every new store is built with. Default for every run. */
export const BRAND_DIRECTION: DesignDirection = {
  id: "coffeeberry", name: "Coffee Berry Standard", style: "modern", mood: "day",
  summary: "The client's brand: light oak + black marble bar, cream walls, black accents, grey tile",
  spec: `This is the CLIENT'S OWN BRAND STANDARD, taken from their built shops and material schedule: reproduce it faithfully, do not reinterpret it.
Floors: architecture(floors=...) "cb_floor" (Soulant grey 60x120) in the shop and WC, "cb_prep_floor" (Ariman grey 30x60) in preparation/kitchen, floor_zone "cb_bar_tile" (COEM Sassiepietre Grigio 90x90) behind the bar. Terrace: "paving".
Ceiling: "rockfon" (seamless white acoustic) everywhere with recessed downlights; WC/prep plain "plaster_white".
Walls: warm cream "#efe4cf" in the shop; WC walls "cb_floor" tile to full height; prep "tile_white" dado. Black "#1b1b1b" for door frames, columns and the window frames.
Bar: counter_run top "cb_oak", front "panel:cb_marble_black" (black marble look), black plinth, no LED kick colour other than warm white; back_bar body "cb_oak" with doors "#1b1b1b", top "cb_oak", splash "cb_marble_black" up to 1.5 m. An oak panel with the coffee-bean dispenser tubes and a wall TV menu_screen over the back bar. Black metal retail shelving_wall where the plan has retail/display.
Light: black dome pendants with warm bulbs over the bar and tables (pendant dome_black), recessed spots, warm 3000 K. Signage: the "coffee berry" logo sign, backlit, on the facade fascia and one interior wall (K.sign("coffee berry", ...)).
Terrace: cream umbrellas "#efe4cf" over the plan's table clusters, grey concrete planters along the edge.
No rattan, no arches, no velvet, no neon, no gallery walls: the brand is clean, warm and simple.`,
};

export const DIRECTIONS: DesignDirection[] = [
  BRAND_DIRECTION,
  {
    id: "japandi", name: "Japandi Calm", style: "japandi", mood: "day",
    summary: "Pale oak, washi white, tatami, quiet black accents",
    spec: `Walls limewash "#e9e3d6"; timber "oak_pale" + "ash" + "hinoki"; floors "oak_pale" boards and "tatami" zones; accents "ebony" and "black_steel". Upholstery "linen:#cfc5b0". Counter front "slat:oak_pale", top "limestone". Signature: ceiling_beams in "hinoki", full-height slat_screen dividers, low lounge_group, one big olive tree inside, rattan or globe pendants, very little on the walls. Facade "#e9e3d6" with "hinoki" band. Restraint: generous empty space.`,
  },
  {
    id: "parisian", name: "Parisian Bistro", style: "bistro", mood: "golden",
    summary: "Panelled walls, brass rails, mosaic floor, bentwood chairs",
    spec: `Walls "#efe6d3" above "panel" dado in "#2f3e36"; floors "tile_check" or "marble_mosaic" and "parquet" in dining; tops "marble_white"; brass everywhere as rails and table edges. Upholstery banquette "leather:#6e2a22" or "velvet:#7a2f2a". Signature: crown mouldings on every wall, arch_mirror pairs, gallery_wall in brass frames, chair variant "bentwood_walnut" or "bentwood_black", fluted globes, striped awnings "#2f3e36" over the glazing, facade "ebony" with "brass" pilasters.`,
  },
  {
    id: "industrial", name: "Warehouse Roastery", style: "industrial", mood: "day",
    summary: "Exposed brick, ducts, concrete, black steel",
    spec: `Walls "brick_red" on feature walls and "concrete" elsewhere; ceiling "concrete_dark" with exposed_duct runs; floor "concrete" polished with "old_boards" in dining; joinery "black_steel" + "old_boards"; counter front "slat:oak_smoked", top "concrete_dark" or "brushed_steel". Upholstery "leather" tan. Signature: track lights, dome_black pendants, metal chairs, long communal table, retail wall of coffee sacks, pendant_linear over counter. Facade "brick_red" plinth "concrete_dark", black framing.`,
  },
  {
    id: "mediterranean", name: "Mediterranean Arches", style: "mediterranean", mood: "golden",
    summary: "Sun-baked plaster, arches, terracotta, rattan",
    spec: `Walls limewash "#ead9c0" and "clay_plaster"; floors "terracotta:#b5673f" tile; bar dado "zellige:#2e6f73" or "zellige:#e9e3d6"; tops "limestone"; joinery "oak". Upholstery "linen:#e2d6bf" with terracotta cushions. Signature: arch_niche sequence with lit bottle shelves on the feature wall, arch_mirror, rattan pendants, many plants and olive trees, ceiling_beams "cedar", facade limewash "#f0e4d0" with "terracotta" plinth and awnings "#a9573a".`,
  },
  {
    id: "deco", name: "Art Deco Noir", style: "deco", mood: "evening",
    summary: "Emerald, marble, brass, velvet, jewel-box lighting",
    spec: `Walls "#1d3a33" lacquer-dark above "panel" dado "mahogany"; floors "parquet_dark" and "marble_nero"; tops "marble_nero" / "marble_white"; lots of "brass". Upholstery "velvet:#6f2a2a" channel banquette and tub chairs. Signature: ceiling_coffers in "plaster_white", pendant_cluster feature, fluted counter "fluted:mahogany" with brass foot rail, arch_mirror in brass, arch_niche back "#7a2f2a". Facade "marble_verde" with "brass" pilasters and cornice, plinth "marble_nero".`,
  },
  {
    id: "midcentury", name: "Mid-Century Lounge", style: "midcentury", mood: "golden",
    summary: "Teak tones, mustard and teal, shell chairs, tulip tables",
    spec: `Walls "#e8dfca" with "veneer:#7a4a2a" full-height panelling and a "#2f6668" accent wall; floor "parquet" herringbone with terrazzo bar zone; counter front "fluted:veneer:#7a4a2a"; tops "terrazzo". Upholstery "velvet:#c49120" and "velvet:#2f6668". Signature: shell chairs on tulip tables, globe pendants on brass, lounge_group with rug, gallery_wall of graphic prints, slat_screen divider. Facade "brick_stone" with "walnut" band and teal awnings "#2f6668".`,
  },
  {
    id: "biophilic", name: "Urban Greenhouse", style: "biophilic", mood: "day",
    summary: "Plants everywhere, sage, pale timber, glassy light",
    spec: `Walls "#dfe4d7" and sage "#9fae95" accent; floors "oak" and "hex_tile:#d9ddd0" at the bar; tops "marble_white"; joinery "ash" with counter front "fluted:ash". Upholstery "velvet:#46624f" and "boucle". Signature: hanging_plants across the ceiling in every zone, many plant() and olive_tree indoors, green dado "zellige:#3f6b52", pendants dome_sage or rattan, slat planter dividers via planter_hedge indoors. Facade "#e7ebdf" with "ash" band and green awnings "#3f6b52".`,
  },
  {
    id: "brutalist", name: "Concrete Gallery", style: "brutalist", mood: "day",
    summary: "Raw concrete, monolithic bar, stainless, gallery light",
    spec: `Walls "concrete" and "concrete_ribbed" feature; ceiling "concrete"; floor "concrete_dark" polished; monolithic counter front "concrete_ribbed", top "brushed_steel"; joinery "brushed_steel" and "ebony"; one colour hit "#c8452b". Upholstery "boucle" and black leather. Signature: very few objects, huge gallery_wall prints, pendant_linear over the bar, black shell chairs, column elements, track lights raking the walls. Facade "concrete" with "concrete_ribbed" band and no awning.`,
  },
  {
    id: "retro", name: "70s Diner Revival", style: "retro", mood: "evening",
    summary: "Terracotta, mustard, walnut, curved booths, neon",
    spec: `Walls "#c9743f" and "#e6c48a" with "beadboard" dado in "veneer:#6b4128"; floors "tile_stone_check" or "terracotta:#a9573a"; tops "terrazzo"; counter front "panel:walnut" with chrome foot rail. Upholstery "velvet:#b0562f" and "velvet:#c49120" channel banquettes. Signature: neon_sign, fluted glass pendants, metal_mustard chairs, cream or terracotta espresso machine, letter_board, big graphic art. Facade "#e6c48a" with "walnut" band and mustard awnings "#c49120".`,
  },
  {
    id: "scandi", name: "Nordic Bakery", style: "scandinavian", mood: "day",
    summary: "White walls, pale oak, blue-grey textile, pure daylight",
    spec: `Walls "plaster_white" and subway tile "subway:#f0ede6" behind the bar; floor "parquet_pale"; tops "marble_white"; joinery "oak_pale" with counter front "panel:oak_pale". Upholstery "linen:#7c8c9a". Signature: open bakery display, bentwood_oak or shell_oak chairs, globe_black pendants, simple wall_shelf runs with ceramics, curtains "linen:#efe9dc" framing glazing, one soft blue "#8fa3b0" accent wall. Facade "plaster_white" with "oak_pale" band.`,
  },
  {
    id: "riad", name: "Moroccan Riad", style: "mediterranean", mood: "evening",
    summary: "Deep zellige, carved arches, warm brass lamps",
    spec: `Dado and bar faces "zellige:#1f5a63"; upper walls "#d8b48a" limewash; floors "tile_diamond" or "marble_mosaic"; tops "marble_white"; joinery "cedar". Upholstery "velvet:#8c2f39" and "linen:#d9c7a6" low banquettes. Signature: arch_niche rows with lit bottles, arch_mirror, brass pendants in clusters, ceiling_beams "cedar", many plants, rugs in deep colours. Facade "#d8b48a" with "zellige:#1f5a63" band, plinth "terracotta:#a9573a".`,
  },
  {
    id: "monochrome", name: "Monochrome Boutique", style: "modern", mood: "day",
    summary: "Black and white with one hot accent, razor-sharp",
    spec: `Walls "plaster_white", one full wall "brick_black"; floor "marble_white" large or "tile_check"; tops "marble_nero"; joinery "ebony" with counter front "fluted:ebony"; hardware "chrome". Accent "#c8a13a" or "#b23a2e" only on tub chairs and one neon. Upholstery "leather:#1a1a1a" and "boucle". Signature: pendant_linear rows, black bentwood or shell chairs, arch_mirror in chrome, gallery_wall in black frames. Facade "ebony" with "marble_white" band.`,
  },
];

export function directionById(id?: string | null): DesignDirection | undefined {
  return DIRECTIONS.find((d) => d.id === id);
}

/** Random direction avoiding the most recent ones (`recent` = newest first). */
export function pickDirection(recent: string[], avoid = 6): DesignDirection {
  const blocked = new Set(recent.slice(0, Math.min(avoid, DIRECTIONS.length - 2)));
  const pool = DIRECTIONS.filter((d) => d.id !== BRAND_DIRECTION.id && !blocked.has(d.id));
  return pool[Math.floor(Math.random() * pool.length)];
}

/** Layout strategies, so room organisation also differs run to run. */
export const LAYOUTS = [
  "Long banquette on the biggest solid wall, 2-tops in front of it, 4-tops by the glazing.",
  "A large communal table down the centre of the dining room, small tables around the edges, a window counter with stools along the glazing.",
  "A lounge zone (lounge_group) at the glazing, banquette at the back, a few round tables between; soft, relaxed.",
  "Booth rhythm: short banquette bays divided by slat_screen or planters, each with its own table and pendant.",
  "Window bar with stools along all the glazing, round tables in clusters mid-room, feature pendant_cluster over the largest cluster.",
];
