// Screenshot the web walkthrough at its tour stops (dev server must be running).
// usage: node scripts/walk-shots.mjs <designId> <outDir> [stops=0,1,2,3] [evening]
import { chromium } from "playwright";
import fs from "node:fs";

const [id, outDir, stopsArg = "0,1,2,3", mode = ""] = process.argv.slice(2);
fs.mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  args: ["--use-angle=vulkan", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
page.on("console", (m) => m.type() === "error" && console.log("console:", m.text().slice(0, 300)));
await page.goto(`http://localhost:3000/zz-walktest?id=${id}${process.env.FX0 ? "&fx=0" : ""}${process.env.Q ? "&q=" + process.env.Q : ""}`);
await page.waitForFunction(() => window.__tour && window.__cafeStats, null, { timeout: 180000 });
await page.evaluate((ev) => {
  const t = window.__tour;
  t.help = false;
  t.mapVisible = false;
  if (ev) t.setEvening?.(true);
  t.emit();
}, mode === "evening");
const stops = stopsArg.split(",").map(Number);
for (const s of stops) {
  await page.evaluate((i) => window.__tour.setNodeImmediate(i), s);
  await page.waitForTimeout(2500);
  await page.screenshot({ path: `${outDir}/stop_${s}${mode ? "_" + mode : ""}.png` });
}
console.log(JSON.stringify(await page.evaluate(() => ({ stats: window.__cafeStats, stops: window.__tour.stops.length }))));
await browser.close();
