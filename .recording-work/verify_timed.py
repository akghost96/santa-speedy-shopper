import json
import math
from pathlib import Path
import re
from statistics import mean
import subprocess

from edit import ROOT, WORK
from timed_edit import duration
import os

LAUNCHER = ROOT / os.environ.get("SANTA_LAUNCHER", "bounty-openclaw")
CAPTURE = WORK / os.environ.get("SANTA_CAPTURE_JSON", "timed-capture.json")
RAW = WORK / os.environ.get("SANTA_RAW", "raw/timed-short-take.webm")
EDIT_JSON = WORK / os.environ.get("SANTA_EDIT_JSON", "timed-edit.json")
HISTORY_OUT = ROOT / os.environ.get("SANTA_HISTORY_OUT", ".benchmarks/timed-live-run.json")

capture = json.loads(CAPTURE.read_text())
raw = RAW
history = json.loads(subprocess.check_output([
    str(LAUNCHER), "gateway", "call", "chat.history", "--json",
    "--params", json.dumps({"sessionKey": capture["sessionKey"], "limit": 40}),
], text=True, cwd=ROOT))
assistant = [message for message in history["messages"] if message.get("role") == "assistant"]
rates = [
    generation["outputTokens"] * 1000 / generation["completionMs"]
    for message in assistant
    if (generation := message.get("serverGeneration"))
]
product_text = next(
    part["text"]
    for message in reversed(assistant)
    for part in message["content"]
    if part.get("type") == "text" and all(link in part["text"] for link in capture["links"])
)
assert history["sessionKey"] == capture["sessionKey"]
assert capture["trusted"] and len(set(capture["links"])) == 5
assert re.search(r"(?m)^\s*5\. ", product_text)
assert rates
official_mean = math.floor(mean(rates) + 0.5)
official_p90 = math.floor(sorted(rates)[math.ceil(len(rates) * 0.9) - 1] + 0.5)
assert capture["score"] == f"{official_mean:,} tok/s mean · {official_p90:,} p90 (server)"
elapsed = capture["finish"] - capture["enter"]
assert 0 < elapsed <= int(os.environ.get("SANTA_CAPTURE_LIMIT", "28000"))
source_length = duration(raw)
video_zero = capture["stoppedAt"] - 1000 * source_length
timing = {
    "start_offset_ms": max(0, capture["ready"] - video_zero - 350),
    "enter_offset_ms": capture["enter"] - video_zero,
    "complete_offset_ms": capture["finish"] - video_zero,
    "elapsed_ms": elapsed,
    "mean_tps": official_mean,
    "p90_tps": official_p90,
    "model_calls": len(rates),
}
assert 0 <= timing["start_offset_ms"] < timing["enter_offset_ms"] < timing["complete_offset_ms"] < source_length * 1000
EDIT_JSON.write_text(json.dumps(timing, indent=2) + "\n")
HISTORY_OUT.write_text(json.dumps(history, indent=2) + "\n")
print(f"{elapsed / 1000:.2f} s from Enter to five links. {capture['score']}.")
