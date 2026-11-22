const { chromium } = await import(new URL("../.bounty-build/node_modules/playwright/index.mjs", import.meta.url).href);
const fs = await import("node:fs");
const links = JSON.parse(fs.readFileSync(process.argv[2], "utf8")).summary.links;
const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true });
const page = await browser.newPage();
for (const url of links) {
  try {
    const r = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
    console.log(r.status(), (await page.title()).slice(0, 70), "|", url);
  } catch (e) { console.log("ERR", e.message.slice(0, 80), url); }
}
await browser.close();
