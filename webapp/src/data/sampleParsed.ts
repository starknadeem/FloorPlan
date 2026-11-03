// A pre-baked, real AI-parsed Coffee Berry scene (captured from a live /api/parse run).
// Used for the welcome screen's "Try a real parsed plan" so a live demo is instant and never fails.

import raw from "./sampleParsedCoffeeBerry.json";
import type { CafeScene } from "@/types/cafescene";

export const sampleParsedScene = raw as unknown as CafeScene;
