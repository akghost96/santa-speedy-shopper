// Headless OpenClaw benchmark: sends one prompt through a gateway's chat.send,
// waits for the final answer, and reports per-call server decode speed
// (Cerebras time_info, the same serverGeneration field the Control UI scores),
// mean / nearest-rank p90, wall time, the tool stage and the returned links.
// Usage: node candidate/bench.mjs <launcher> <label> [prompt]
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const project = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [launcher, label, promptArg] = process.argv.slice(2);
if (!launcher || !label) throw new Error("usage: bench.mjs <launcher> <label> [prompt]");
const prompt =
  promptArg ?? "Find five Christmas gifts from US retailers. Give me five direct product links.";
const limitMs = Number(process.env.BENCH_LIMIT_MS ?? 60000);
const sessionKey = `agent:main:bench-${label}-${Date.now()}`;

const call = (method, params) =>
  JSON.parse(
    execFileSync(launcher, ["gateway", "call", method, "--json", "--params", JSON.stringify(params)], {
      encoding: "utf8",
      timeout: 20000,
      stdio: ["ignore", "pipe", "pipe"],
    }),
  );

const sentAt = Date.now();
call("chat.send", { sessionKey, message: prompt, idempotencyKey: `bench-${sentAt}` });
let messages = [];
let final;
while (Date.now() - sentAt < limitMs) {
  try {
    messages = call("chat.history", { sessionKey, limit: 200 }).messages ?? [];
  } catch {
    // Retryable gateway errors (e.g. session storage warming up): poll again.
  }
  final = messages.findLast((m) => m.role === "assistant" && m.stopReason && m.stopReason !== "toolUse");
  if (final) break;
  await new Promise((r) => setTimeout(r, 150));
}
const seenAt = Date.now();
if (!final) {
  try { call("chat.abort", { sessionKey }); } catch {}
  console.error(`No final answer within ${limitMs / 1000}s; aborted ${sessionKey}`);
  process.exit(75);
}

const calls = messages
  .filter((m) => m.role === "assistant")
  .map((m) => {
    const g = m.serverGeneration;
    return {
      stopReason: m.stopReason,
      outputTokens: g?.outputTokens ?? m.usage?.output,
      completionMs: g?.completionMs,
      tps: g ? g.outputTokens / (g.completionMs / 1000) : null,
      input: m.usage?.input,
      cacheRead: m.usage?.cacheRead,
      tools: (m.content ?? []).filter((c) => c.type === "toolCall").map((c) => `${c.name}(${JSON.stringify(c.arguments)})`),
      thinkingChars: (m.content ?? []).filter((c) => c.type === "thinking").reduce((n, c) => n + c.thinking.length, 0),
    };
  });
const rates = calls.map((c) => c.tps).filter((v) => Number.isFinite(v));
const sorted = [...rates].sort((a, b) => a - b);
const mean = rates.reduce((a, b) => a + b, 0) / rates.length;
const p90 = sorted[Math.max(0, Math.ceil(0.9 * sorted.length) - 1)];
const text = (final.content ?? []).filter((c) => c.type === "text").map((c) => c.text).join("\n");
const links = [...new Set([...text.matchAll(/\]\((https:\/\/[^)\s]+)\)/g)].map((m) => m[1]))];
const toolResults = messages.filter((m) => m.role === "toolResult").map((m) => ({
  tool: m.toolName,
  isError: m.isError,
  text: (m.content ?? []).map((c) => c.text ?? "").join("").slice(0, 4000),
}));
const resultText = toolResults.map((r) => r.text).join("\n");
const user = messages.find((m) => m.role === "user");
// Provider errors that OpenClaw retried inside this run (e.g. Cerebras 429 queue).
const stateDir = path.join(path.dirname(path.resolve(launcher)), "..", process.env.BENCH_STATE ?? ".candidate-state");
let providerRetries = null;
try {
  providerRetries = readFileSync(path.join(stateDir, "gateway.log"), "utf8")
    .split("\n")
    .filter((l) => l.includes(`runId=bench-${sentAt} isError=true`)).length;
} catch {}
const summary = {
  label,
  sessionKey,
  prompt,
  calls,
  meanTps: Math.round(mean),
  p90Tps: Math.round(p90),
  providerRetries,
  wallClientMs: seenAt - sentAt,
  wallTranscriptMs: (final.__openclaw?.recordTimestampMs ?? final.timestamp) - (user?.timestamp ?? sentAt),
  numberedLines: text.split("\n").filter((l) => /^\s*\d+\.\s/.test(l)).length,
  links,
  distinctHosts: new Set(links.map((u) => new URL(u).host)).size,
  linksFromToolResults: links.filter((u) => resultText.includes(u)).length,
  answer: text,
};
mkdirSync(path.join(project, ".benchmarks/candidate"), { recursive: true });
const out = path.join(project, ".benchmarks/candidate", `${label}.json`);
writeFileSync(out, JSON.stringify({ summary, toolResults, messages }, null, 2));
const { answer, ...brief } = summary;
console.log(JSON.stringify(brief, null, 1));
console.log(answer);
console.log(`saved ${out}`);
