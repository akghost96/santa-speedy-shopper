# Changes to OpenClaw

**OpenClaw's source is not modified beyond the official speed patch.**

The build used for the entry is OpenClaw commit `8b18b5578f66eab1501cba4cef2310d88bfb9a41` with
`official-openclaw-speed.patch` applied by `git am` (two commits) and nothing else. The patch file in this repo is
byte-identical to `openclaw-cerebras-kimi-on-8b18b55.patch` in `wkasekende/openclaw-speed-patch`.

Output of `scripts/verify-openclaw-build.sh` on the build that made the entry (2026-11-22):

```
patch file sha256:   c964a28808c8d9e33aaaa2897dea951e595dd35c2d4047484eb6e5e97059c9c0
base is an ancestor: yes
commits on top of the base:
  e7165e62 docs(dev): example config for Kimi on Cerebras's chat completions API
  557906cb feat(chat): show Cerebras's decode speed as mean tok/s per response and session
patch-ids in the patch file:
  f916a1a5fdcfa3fe0eef14f0948dbd8d93199ab5
  9d6aad4b80fbfd7b9b9ce730f54ba408ffdf4f6e
patch-ids of those commits:
  f916a1a5fdcfa3fe0eef14f0948dbd8d93199ab5
  9d6aad4b80fbfd7b9b9ce730f54ba408ffdf4f6e
uncommitted or untracked changes: none
```

The checkout was patched at 09:30 and built at 09:31–09:33 the same day; the gateway runs from that build.

## What does change OpenClaw's behaviour

Everything below is configuration or a plugin loaded through OpenClaw's own plugin system. None of it edits
OpenClaw's files.

| Where | What it changes |
| --- | --- |
| `candidate/openclaw.example.json` | Model and provider (the patch's example values), temperature 0, thinking `low`, heartbeat off, tool profile `minimal` with only `search_catalog` allowed, Code Mode and tool search off, the plugin enabled |
| `candidate/santa-catalog/index.mjs`, tool | Adds the `search_catalog` tool (live Shopify catalog search) |
| same file, system prompt | Adds the `## Shopping` block quoted in `README.md` through the provider hook `resolveSystemPromptContribution` |
| same file, provider | Registers as the runtime owner of the `cerebras` provider in place of the bundled Cerebras plugin, to wrap its stream function. The wrapper sets `tool_choice` and `max_completion_tokens`, inserts one example turn into the request, and retries requests that Cerebras's queue rejected or held for more than 8 s before any output. Responses, `usage` and `time_info` pass through unchanged |

## What the recording adds

`.recording-work/capture-timed.mjs` drives the web chat with Playwright and injects one element into the page while
recording: the stopwatch box in the top-left corner. It does not touch the patch's speed badge.
`.recording-work/timed_edit.py` adds the title strip and the closing score card to the video.
