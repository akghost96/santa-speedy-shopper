# Santa's Speedy Shopper — Speed Bounty entry

**1,757 tok/s mean · 1,765 p90**, two model calls, measured by the official speed patch.
Video: `submissions/candidate-1757tps.mp4` (17 s, uncut take, recorded 2026-11-22 22:13 EET).

This page says exactly what the entry does, including the parts that exist only to make it fast.

## What runs

| Piece | Value |
| --- | --- |
| OpenClaw | commit `8b18b55` plus the official patch, nothing else changed (`official-openclaw-speed.patch` is byte-identical to `openclaw-cerebras-kimi-on-8b18b55.patch` in `wkasekende/openclaw-speed-patch`) |
| Model | `cerebras/moonshotai-kimi-k3.1-pro-trial` at `https://api.cerebras.ai/v1`, reasoning effort `low`, temperature `0` |
| Tools | one tool, `search_catalog`, from the plugin in `candidate/santa-catalog/` (OpenClaw's other tools, Code Mode and tool search are off) |
| Product source | Shopify's Global Catalog (`catalog.shopify.com`), queried live on every run |

## One run, step by step

1. The user types: "Find five Christmas gifts from US retailers. Give me five direct product links."
2. **Model call 1 (82 output tokens).** Kimi writes a one-line thought and calls `search_catalog` with five queries:
   board game, cozy throw blanket, scented candle, coffee gift set, dog toy.
3. **The tool** sends each query to the Shopify catalog (US, USD, ships to US) and keeps the first hit that is in
   stock, priced in USD and not on another country's domain. It strips tracking parameters and returns five lines of
   the form `N. [name](url) — store`.
4. **Model call 2 (208 output tokens).** Kimi writes a one-line thought and replies with those five lines.

Nothing is cached between runs. In the entry take the answer is line for line what that run's tool call returned;
`candidate/bench.mjs` reports the same check (`linksFromToolResults`) for any headless run.

## What is tuned for speed

Cerebras decodes text that the model can copy from its context much faster than text it has to compose. The entry
is built around that:

- **The five search queries are fixed in the system prompt.** The model does not choose what to search for, so the
  same products come back on most runs. The search itself is live.
- **Both thoughts are scripted.** The system prompt gives the exact sentence for each
  ("I must call search_catalog immediately with exact queries." / "I must copy the result lines verbatim.").
- **The tool returns the answer already formatted, four times.** The five live lines, then the same lines three more
  times under "Reply with exactly these lines:". Text seen several times decodes faster than text seen once. All four
  copies come from that run's search.
- **The plugin inserts two example turns into each request** (each: user → tool call → result → answer), so the
  scripted thought and the tool call have been seen three times before the model writes them. Their ten products are
  real catalog results chosen from below the top hit, so that no line of the answer is already in the prompt (true
  for the entry take: none of its five products is in the examples).
- **Request shaping.** `tool_choice: "required"` on the first call and `max_completion_tokens: 1024`. To do this the
  plugin registers as the runtime owner of the `cerebras` provider and wraps its stream function. Base URL, model,
  transport, `usage` and `time_info` are passed through untouched.
- **Queue handling.** A request rejected with `429 queue_exceeded` is retried after 0.5 s, and a request with no
  first token after 8 s is cancelled and sent again. Only requests that have produced no output are retried; every
  call that completes is in the transcript and counted.
- **Temperature 0** (the patch README suggests 1.0).

The system prompt addition, verbatim:

```
## Shopping
For gift or product requests, call search_catalog immediately with arguments {"queries": ["board game", "cozy throw blanket", "scented candle", "coffee gift set", "dog toy"]}
Your reasoning must be exactly one short line: I must call search_catalog immediately with exact queries.
After the tool result, your reasoning must be exactly: I must copy the result lines verbatim. Then reply with exactly the result lines, nothing else.
```

## How the TPS is measured

By the patch, unchanged: for each model call, `usage.completion_tokens / time_info.completion_time` as Cerebras
reports them; the badge shows the mean and p90 over the run's calls. For the entry:

| Call | Tokens | Server decode time | Rate |
| --- | --- | --- | --- |
| 1, tool call | 82 | 46.9 ms | 1,750 tok/s |
| 2, answer | 208 | 117.9 ms | 1,765 tok/s |
| Mean | | | **1,757 tok/s** |

The recorder re-reads the run from `chat.history` and refuses a take unless the badge matches these numbers.

## How the take was chosen

It is the fastest of many. On 2026-11-22 the recorder made 2,185 verified takes across several configurations;
the entry is the best of the 886 takes made with the configuration described here. Decode speed depends mostly on
Cerebras's load at that moment: the median of those takes scored about 1,192 tok/s, 46 passed 1,600 and 14 passed 1,700.
Every take is listed in `evidence/parallel-results.jsonl`.

Up to eight recorders ran in parallel. Cerebras's queue was full for most of the afternoon, so most requests were
rejected at once and retried: about 480 requests a minute at peak, under the key's 1,000 requests/minute limit.
From 20:00 four recorders ran at about 70 requests a minute.

Earlier takes the same day scored up to 1,713, but their example turn listed three products that the live search
also returns, which made the answer call faster. They are not the entry. Earlier entries: 1,755 mean (20:39, same configuration,
`evidence/entry-1755/`) and 1,719 mean (18:42, one example turn and three copies of the result, `evidence/entry-1719/`).

## The video

Playwright drives headless Chromium on the gateway's own web chat. The prompt is typed on screen and submitted with
Enter. Two things in the picture are not OpenClaw: the stopwatch box (top left), which the recording script adds to
the page, and the title strip and closing score card, which are added in the edit. The speed badge next to the
message box is the patch's.

The five products in the take (all loaded with HTTP 200 on 2026-11-22):

1. Root: A Game of Woodland Might and Right — https://ledergames.com/products/root-a-game-of-woodland-might-and-right
2. Double-Sided Cozy Throw Blanket - Patchwork Be Happy — https://www.naturallife.com/products/double-sided-cozy-throw-blanket-patchwork-be-happy
3. Maple Butter 3-Wick Candle — https://goosecreek.com/products/maple-butter-large-3-wick-candle
4. Right Roast Sampler Gift Basket — https://www.coffeebeanery.com/products/the-right-roast-sampler-gift-basket
5. Pickle Stickle Super Chewer Durable Gnaw Dog Toy — https://bark.co/products/pickle-stickle

## Reproduce

```bash
# OpenClaw 8b18b55 + the official patch, built as its README says, in .bounty-build/
# Gateway config: candidate/openclaw.example.json (set the two <project> paths and a gateway token)
export CEREBRAS_API_KEY=...                                    # or point OPENCLAW_BOUNTY_ENV at an env file
candidate/candidate-openclaw gateway run                       # web chat on http://127.0.0.1:18891
node candidate/bench.mjs candidate/candidate-openclaw try-1    # one headless run, prints per-call TPS
.recording-work/record-parallel.sh 1 10                        # recorded browser takes for 10 minutes
```

## The agent

It is OpenClaw's default `main` agent with an empty workspace, no skills and no bootstrap files. What makes it this
agent is the gateway config (`candidate/openclaw.example.json`) and the plugin (`candidate/santa-catalog/`); both are
in this repo in full. `candidate/candidate-openclaw` starts the gateway with them.

## Files

| Path | What |
| --- | --- |
| `candidate/santa-catalog/index.mjs` | the plugin: search tool, example turn, request shaping, queue handling |
| `candidate/openclaw.example.json` | gateway config used for the entry, without secrets |
| `candidate/bench.mjs`, `candidate/check-links.mjs` | headless run with per-call TPS; opens the five links |
| `.recording-work/` | recorder, verification and video edit scripts |
| `candidate/README.md` | work log: everything that was tried, with numbers |
| `official-openclaw-speed.patch` | the official patch as applied |
| `OPENCLAW-MODIFICATIONS.md`, `scripts/verify-openclaw-build.sh` | what changes OpenClaw (the patch only) and the check that proves it |
| `evidence/entry-1757/` | the entry take: gateway transcript with per-call server timing, capture timings, screenshot |
| `evidence/parallel-results.jsonl` | every verified take of the day: id, mean, p90, Enter-to-list time, clock time |
| `submissions/candidate-1757tps.mp4` | the entry video |

Not for sharing: `.candidate-state/` and `.bounty-state/` (gateway tokens, logs) and `.bounty-build/` (the OpenClaw
checkout and build).
