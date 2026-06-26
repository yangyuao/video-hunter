// Headless verification of the full UI (graph + videos modes): loads the app,
// asserts the graph renders with no console errors, exercises selection +
// filtering, then switches to the video explorer and checks the list, player
// and provenance detail. Run from frontend/: node scripts/verify-graph.mjs
import { chromium } from "playwright";

const URL = process.env.APP_URL || "http://127.0.0.1:8000/";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

const errors = [];
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
});
page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));

const t0 = Date.now();
await page.goto(URL, { waitUntil: "networkidle" });
await page.locator(".graph-canvas canvas").first().waitFor({ timeout: 15000 });
const loadMs = Date.now() - t0;

await page.waitForTimeout(1500); // let fcose settle

const barText = (await page.locator(".graph-bar .muted").textContent()) || "";
await page.screenshot({ path: "scripts/shot-graph.png" });

// --- Graph: click a real node, expect detail panel + neighbor highlight ---
const nodeInfo = await page.evaluate(() => {
  const cy = window.__cy;
  if (!cy || cy.nodes().length === 0) return null;
  const node = cy.nodes()[0];
  const box = document.querySelector(".graph-canvas").getBoundingClientRect();
  const pos = node.renderedPosition();
  return { x: Math.round(pos.x + box.left), y: Math.round(pos.y + box.top), total: cy.nodes().length };
});

let detailOk = false;
let neighborHighlight = null;
if (nodeInfo) {
  await page.mouse.click(nodeInfo.x, nodeInfo.y);
  try {
    await page.locator(".detailbar .account-name").waitFor({ timeout: 5000 });
    detailOk = true;
  } catch {}
  neighborHighlight = await page.evaluate(() => {
    const cy = window.__cy;
    const sel = cy.nodes().filter(".selected");
    const nbhd = sel.closedNeighborhood();
    return {
      hasSel: sel.length === 1,
      fadedNonNbhd: cy.elements().not(nbhd).filter(".faded").length,
    };
  });
}
const neighborOk = !!(neighborHighlight && neighborHighlight.hasSel && neighborHighlight.fadedNonNbhd > 0);
await page.screenshot({ path: "scripts/shot-selected.png" });

// toggle a relationship filter off/on (class-toggle path, no rebuild)
await page.locator(".sidebar label.check", { hasText: "转发" }).locator("input").uncheck();
await page.waitForTimeout(200);
await page.locator(".sidebar label.check", { hasText: "转发" }).locator("input").check();
await page.waitForTimeout(200);

// --- Videos mode ---
await page.locator(".mode-toggle button", { hasText: "视频" }).click();
await page.locator(".video-item").first().waitFor({ timeout: 10000 });
const videoCount = await page.locator(".video-item").count();

// open the first video, expect player + provenance detail
let videoDetailOk = false;
let occurrenceCount = 0;
await page.locator(".video-item").first().click();
try {
  await page.locator(".player-title").waitFor({ timeout: 6000 });
  // occurrences / evidence sections may or may not exist; count if present
  occurrenceCount = await page.locator(".occ").count();
  videoDetailOk = true;
} catch {}
await page.screenshot({ path: "scripts/shot-videos.png" });

await browser.close();

const ok = errors.length === 0 && detailOk && neighborOk && videoCount > 0 && videoDetailOk;
console.log(JSON.stringify({
  loadMs,
  nodeCount: nodeInfo?.total ?? null,
  barText: barText.trim(),
  graph_detailOnSelect: detailOk,
  graph_neighborHighlight: neighborHighlight,
  videos_listCount: videoCount,
  videos_detailOnOpen: videoDetailOk,
  videos_occurrenceRows: occurrenceCount,
  consoleErrors: errors,
  ok,
}, null, 2));
process.exit(ok ? 0 : 1);
