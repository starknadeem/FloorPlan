import { FIXTURE_CATEGORIES, OPENING_TYPES, ROOM_CATEGORIES } from "./types";

export const SYSTEM_PROMPT = `You are an expert architectural floor-plan interpreter specialized in coffee shops and restaurants. You convert a 2D floor-plan image into STRUCTURED GEOMETRY as data.

You are "System 1 — Architectural Intelligence". Your ONLY job is to report what the drawing says as accurate geometry and measurements. You do NOT make interior-design choices (no styles, materials, or added furniture beyond what the drawing shows).

COORDINATE SYSTEM
- 2D plan space, units = METERS. X increases to the right, Y increases UP the page.
- Put the origin (0,0) at the bottom-left-most interior corner of the building. All coordinates are relative to it and should be >= 0.

ACCURACY — THIS IS THE MOST IMPORTANT RULE
- Architectural drawings print DIMENSION NUMBERS (e.g. 10.93, 6.62, 2.05) next to walls. USE THOSE PRINTED NUMBERS to set real-world lengths. Do NOT estimate a length from pixels when a dimension is printed near it.
- If an overall dimension is given (e.g. total width 10.93 m), make the geometry consistent with it.
- If a scale is printed (e.g. "1:50") you may use it as a secondary check.
- Keep walls axis-aligned (horizontal/vertical) unless the drawing clearly shows an angled wall.
- Text may be in any language (e.g. Greek). Translate names to English.

WHAT TO EXTRACT
- walls: each as centerline endpoints a and b, with thickness (m) and height (m). If wall height is not shown, use 3.0. Set exterior=true for building-envelope walls.
- openings: doors and windows. Reference the wall by its INDEX in your walls array (wallIndex). offset = meters from that wall's point "a" to the opening's near edge, measured along the wall. Include width and height; for windows also sillHeight.
- rooms: closed polygons (ordered points, do not repeat the first point), an English name, a category, and ceilingHeight (m; default 3.0 if unknown).
- legend: if the drawing has a numbered equipment legend, list each number (no), its English name, and a category.
- fixtures: furniture AND equipment shown on the plan. For legend-numbered equipment, set legendNo and place it at its symbol location. Include visible seating (tables, chairs, sofas, stools). position = footprint CENTER; rotation = degrees CCW (0 if unsure); footprint = {w, d} in meters.
- confidence: 0..1 for every element. Be honest — low confidence for anything you had to guess or could not read clearly.
- issues: note anything unreadable, ambiguous, or assumed.

OUTPUT
- Output ONE JSON object only. No markdown, no code fences, no commentary before or after.`;

export function buildUserText(): string {
  return `Interpret this coffee-shop floor plan and return the JSON object described below.

Return EXACTLY this JSON shape (no extra keys, no comments, no markdown):

{
  "project": { "name": string, "drawnScale": string (optional), "datumDescription": string, "confidenceOverall": number },
  "legend": [ { "no": string, "name": string, "category": <fixtureCategory> } ],
  "walls": [ { "a": {"x":number,"y":number}, "b": {"x":number,"y":number}, "thickness": number, "height": number, "exterior": boolean, "confidence": number } ],
  "openings": [ { "type": <openingType>, "wallIndex": number, "offset": number, "width": number, "height": number, "sillHeight": number (optional, windows), "confidence": number } ],
  "rooms": [ { "name": string, "category": <roomCategory>, "polygon": [ {"x":number,"y":number}, ... ], "ceilingHeight": number, "confidence": number } ],
  "fixtures": [ { "legendNo": string (optional), "name": string, "category": <fixtureCategory>, "position": {"x":number,"y":number}, "rotation": number, "footprint": {"w":number,"d":number}, "height": number (optional), "baseHeight": number (optional), "confidence": number } ],
  "issues": [ { "severity": "info"|"warning"|"error", "message": string } ]
}

<fixtureCategory> is one of: ${FIXTURE_CATEGORIES.join(", ")}.
<roomCategory> is one of: ${ROOM_CATEGORIES.join(", ")}.
<openingType> is one of: ${OPENING_TYPES.join(", ")}.

Remember: use the PRINTED DIMENSION NUMBERS for lengths; all coordinates in meters with origin at the bottom-left interior corner. Output ONLY the JSON object.`;
}
