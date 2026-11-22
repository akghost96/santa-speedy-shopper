import json
import math
import os
from pathlib import Path
import subprocess
import sys

from edit import ACCENT, ENCODE, MUTED, OPENING, ROOT, WORK, footage, join, still, text, video


def duration(source):
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(source),
    ], text=True).strip())


def scoreboard(draw, run):
    text(draw, (84, 116), os.environ.get("SANTA_SCORE_TITLE", "Cerebras official speed patch"), 34, bold=True)
    text(draw, (80, 220), f"{run['mean_tps']:,}", 180, ACCENT, True)
    text(draw, (90, 430), "mean tokens/sec", 54, bold=True)
    text(draw, (90, 525), f"{run['p90_tps']:,} p90  ·  {run['model_calls']} model calls", 30, MUTED)
    text(draw, (90, 682), f"Enter to five product links   {run['elapsed_ms'] / 1000:.2f} s", 32, bold=True)


def stitch(first, second, gap):
    def describe_pause(draw):
        text(draw, (84, 281), "Capture resumes", 58, bold=True)
        text(draw, (88, 380), f"{gap:.1f} s between clips. The stopwatch kept running.", 31, MUTED)

    inputs = [ROOT / first]
    if gap >= 0.1:
        inputs.append(still("timed-capture-gap", gap, describe_pause))
    inputs.append(ROOT / second)
    args = [arg for entry in inputs for arg in ("-i", str(entry))]
    pieces = [
        f"[{index}:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[part{index}]"
        for index in range(len(inputs))
    ]
    clip_labels = "".join(f"[part{index}]" for index in range(len(inputs)))
    pieces.append(f"{clip_labels}concat=n={len(inputs)}:v=1:a=0[out]")
    target = WORK / "timed-stitched-source.mp4"
    video([*args, "-filter_complex", ";".join(pieces), "-map", "[out]", *ENCODE, str(target)])
    return target


def live(source, run):
    source = ROOT / source
    length = duration(source)
    lead = run.get("start_offset_ms", 0) / 1000
    click = run["enter_offset_ms"] / 1000
    shown = run["complete_offset_ms"] / 1000
    assert 0 <= lead < click < shown < length

    right = "Kimi K3.1 Pro on Cerebras"
    score = still("timed-score", 4.4, lambda draw: scoreboard(draw, run))
    if length - lead + 4.4 <= 59.8:
        take = footage(
            "timed-continuous", source, lead, length - lead,
            "Santa’s Speedy Shopper", right, OPENING,
        )
        join(os.environ.get("SANTA_VIDEO_OUT", "santa-speed-bounty-timed-review"), [take, score])
        return

    first_length = click + 1.1
    tail_start = shown - 1.25
    wait_length = tail_start - first_length
    tail_length = length - tail_start
    speed = max(2, math.ceil(wait_length / (59.4 - first_length + lead - tail_length - 4.4)))

    first = footage(
        "timed-typing-enter", source, lead, first_length - lead,
        "Santa’s Speedy Shopper", right, OPENING,
    )
    accelerated = WORK / "timed-accelerated-source.mp4"
    video([
        "-i", str(source), "-vf",
        (f"fps=30,trim=start={first_length}:end={tail_start},"
         f"setpts=(PTS-STARTPTS)/{speed},fps=30"),
        *ENCODE, str(accelerated),
    ])
    wait = footage(
        "timed-wait", accelerated, 0, duration(accelerated),
        f"Waiting · {speed}× playback", "Stopwatch shows actual elapsed time", OPENING,
    )
    tail = footage(
        "timed-list", source, tail_start, tail_length,
        "Five product links", right, OPENING,
    )
    join(os.environ.get("SANTA_VIDEO_OUT", "santa-speed-bounty-timed-review"), [first, wait, tail, score])
    uncut = footage(
        "timed-uncut", source, lead, length - lead,
        "Santa’s Speedy Shopper", right, OPENING,
    )
    join(os.environ.get("SANTA_VIDEO_FULL", "santa-speed-bounty-full"), [uncut, score])


if __name__ == "__main__":
    run = json.loads(Path(sys.argv[2]).read_text())
    recording = sys.argv[1]
    if "second_clip" in run:
        recording = stitch(recording, run["second_clip"], run["gap_ms"] / 1000)
    live(recording, run)
