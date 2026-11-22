import fs from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "../.bounty-build/node_modules/playwright/index.mjs";

const project = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const work = path.join(project, ".recording-work");
// Defaults record the official build on 18890; the candidate uses
// SANTA_PORT=18891 SANTA_STATE=.candidate-state SANTA_LAUNCHER=candidate/candidate-openclaw.
const port = process.env.SANTA_PORT ?? "18890";
const launcher = path.join(project, process.env.SANTA_LAUNCHER ?? "bounty-openclaw");
const rawName = process.env.SANTA_RAW ?? "raw/timed-short-take.webm";
const captureJson = process.env.SANTA_CAPTURE_JSON ?? "timed-capture.json";
const resultPng = process.env.SANTA_RESULT_PNG ?? "timed-result.png";
process.env.OPENCLAW_STATE_DIR = path.join(project, process.env.SANTA_STATE ?? ".bounty-state");
process.env.OPENCLAW_CONFIG_PATH = path.join(process.env.OPENCLAW_STATE_DIR, "openclaw.json");
const { n: issueHandoff } = await import("../.bounty-build/dist/control-ui-handoff-BEDtjids.mjs");
const origin = `http://127.0.0.1:${port}`;
const sessionKey = process.env.SANTA_CAPTURE_KEY;
const captureLimit = Number(process.env.SANTA_CAPTURE_LIMIT);
if (!sessionKey?.startsWith("agent:main:bounty-short-") || captureLimit < 1000) {
  throw new Error("A dedicated take and time limit are required");
}
const { browserUrl } = await issueHandoff({
  httpUrl: `${origin}/chat?session=${encodeURIComponent(sessionKey)}`,
  wsUrl: `ws://127.0.0.1:${port}`,
});

const prompt = "Find five Christmas gifts from US retailers. Give me five direct product links.";
const viewport = { width: 1440, height: 810 };
const browser = await chromium.launch({
  executablePath: "/usr/bin/chromium",
  headless: true,
});
const staging = await fs.mkdtemp(path.join(work, "timed-capture-"));
let context;
let page;
let result;
let stoppedAt;
const captureStart = Date.now();

try {
  context = await browser.newContext({
    colorScheme: "dark", viewport, recordVideo: { dir: staging, size: viewport },
  });
  page = await context.newPage();
  await page.goto(browserUrl, { waitUntil: "domcontentloaded", timeout: 15000 });
  const box = page.getByRole("textbox", { name: "Chat composer", exact: true });
  await box.waitFor({ state: "visible", timeout: 20000 }).catch(async (error) => {
    await page.screenshot({ path: path.join(work, resultPng.replace(/\.png$/, ".fail.png")) });
    throw error;
  });
  const collapse = page.getByRole("button", { name: "Collapse sidebar", exact: true });
  if (await collapse.isVisible()) await collapse.click();
  await box.focus();
  await page.evaluate(() => {
    const badge = document.createElement("div");
    badge.setAttribute("aria-hidden", "true");
    badge.style.cssText = "position:fixed;left:25px;top:72px;width:225px;box-sizing:border-box;padding:15px 18px 16px;z-index:99999;pointer-events:none;background:#172121;border:1px solid #445f4e;border-radius:13px;color:#eef3eb;font-family:system-ui,sans-serif;box-shadow:0 7px 20px #0004";
    const key = document.createElement("div");
    const digits = document.createElement("div");
    const status = document.createElement("div");
    key.style.cssText = "font-size:16px;font-weight:650;letter-spacing:.02em;color:#c8f884";
    digits.style.cssText = "font-size:41px;font-weight:700;line-height:1.2;letter-spacing:-.04em;font-variant-numeric:tabular-nums;margin:6px 0 5px";
    status.style.cssText = "font-size:14px;color:#bbc8c0";
    key.textContent = "Enter → 5 product links";
    digits.textContent = "0.00 s";
    status.textContent = "Ready";
    badge.append(key, digits, status);
    document.body.append(badge);

    const now = () => performance.timeOrigin + performance.now();
    const take = window.__bountyTake = {
      ready: now(), enter: null, finish: null, links: [], trusted: false,
    };
    const target = document.body;
    const getLinks = () => [...new Set(
      [...target.querySelectorAll('main ol li a[href^="https://"]')].filter((link) => {
        const rect = link.getBoundingClientRect();
        return rect.height > 0 && rect.bottom > 0 && rect.top < innerHeight;
      }).map(link => link.href)
    )];
    const update = () => {
      if (take.enter === null || take.finish !== null) return;
      const stamp = now();
      const links = getLinks();
      const elapsed = (stamp - take.enter) / 1000;
      if (links.length >= 5) {
        take.finish = stamp;
        take.links = links.slice(0, 5);
        key.textContent = "Timer stopped";
        status.textContent = "5 product links visible";
        digits.style.color = "#c8f884";
      } else {
        const label = elapsed < 0.95 ? "Enter pressed" : "Waiting for the list";
        if (status.textContent !== label) status.textContent = label;
      }
      const time = elapsed.toFixed(2) + " s";
      if (digits.textContent !== time) digits.textContent = time;
    };
    const observer = new MutationObserver((changes) => {
      if (take.enter !== null && take.finish === null && changes.some((change) => !badge.contains(change.target))) {
        requestAnimationFrame(update);
      }
    });
    observer.observe(target, { childList: true, subtree: true, characterData: true });
    setInterval(update, 55);
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || event.shiftKey || take.enter !== null) return;
      take.enter = performance.timeOrigin + event.timeStamp;
      take.trusted = event.isTrusted;
      key.textContent = "Enter ↵";
      status.textContent = "Enter pressed";
      update();
    }, true);
  });
  await page.waitForTimeout(550);
  await box.pressSequentially(prompt, { delay: 57 });
  if (await box.inputValue() !== prompt) throw new Error("Visible prompt did not match");
  await page.waitForTimeout(650);
  await page.keyboard.press("Enter");
  process.stdout.write("Prompt typed and submitted with Enter. Waiting for the fifth link.\n");

  const received = await page.waitForFunction(() => {
    const take = window.__bountyTake;
    const main = document.querySelector("main");
    const stats = main.innerText.match(/[0-9,.]+ tok\/s mean · [0-9,.]+ p90 \(server\)/g);
    return take?.finish && stats?.length && !main.innerText.includes("Assistant is working...");
  }, undefined, { polling: 150, timeout: captureLimit }).catch((error) => {
    if (error.name !== "TimeoutError") throw error;
    return null;
  });
  if (received) {
    // The server-TPS badge can show only the final call for a moment before the
    // earlier call's serverGeneration lands; read it once it has settled.
    const readScore = () => page.evaluate(() => document.querySelector("main").innerText
      .match(/[0-9,.]+ tok\/s mean · [0-9,.]+ p90 \(server\)/g).at(-1));
    let score = await readScore();
    for (let stableSince = Date.now(), until = Date.now() + 6000; Date.now() < until;) {
      await page.waitForTimeout(250);
      const next = await readScore();
      if (next !== score) { score = next; stableSince = Date.now(); }
      else if (Date.now() - stableSince >= 2500) break;
    }
    result = await page.evaluate((score) => ({
      ...window.__bountyTake,
      score,
      path: location.pathname,
    }), score);
    await page.screenshot({ path: path.join(work, resultPng) });
    await page.waitForTimeout(1200);
    stoppedAt = Date.now();
  } else {
    execFileSync(launcher, [
      "gateway", "call", "chat.abort", "--json", "--params", JSON.stringify({ sessionKey }),
    ], { stdio: "pipe", timeout: 5000 });
    process.stdout.write(`No complete answer within ${captureLimit / 1000} s. Starting a fresh take.\n`);
  }
} finally {
  const recording = page?.video();
  await context?.close();
  if (recording && result) await recording.saveAs(path.join(work, rawName));
  await browser.close();
  await fs.rm(staging, { recursive: true, force: true });
}
if (!result) {
  process.exitCode = 75;
} else {
  if (!result.trusted || result.links.length !== 5) throw new Error("Missing live timing evidence");
  await fs.writeFile(path.join(work, captureJson), JSON.stringify({
    ...result, captureStart, stoppedAt, sessionKey, prompt,
  }, null, 2) + "\n", { mode: 0o600 });
  process.stdout.write(`Five links appeared after ${((result.finish - result.enter) / 1000).toFixed(2)} s. ${result.score}.\n`);
}
