from pathlib import Path
import json
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / ".recording-work"
SIZE = 1440, 810
BG = "#111619"
INK = "#F2F5F1"
MUTED = "#AFBDB7"
ACCENT = "#C8F884"
EARLIER = "#7F9291"
FONT_ROOT = Path("/usr/share/fonts/noto")


def text(draw, point, content, size, color=INK, bold=False):
    font = ImageFont.truetype(FONT_ROOT / f"NotoSans-{'Bold' if bold else 'Regular'}.ttf", size)
    draw.text(point, content, font=font, fill=color, anchor="lt")


def card(name, painter):
    img = Image.new("RGB", SIZE, BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((84, 86, 161, 91), fill=ACCENT)
    painter(draw)
    target = WORK / f"{name}.png"
    img.save(target)
    return target


def header(name, left, right=None):
    img = Image.new("RGBA", SIZE)
    draw = ImageDraw.Draw(img)
    text(draw, (64, 19), left, 25, bold=True)
    if right:
        font = ImageFont.truetype(FONT_ROOT / "NotoSans-Regular.ttf", 22)
        draw.text((1376, 22), right, font=font, fill=MUTED, anchor="rt")
    target = WORK / f"{name}.png"
    img.save(target)
    return target


def intro(draw, subtitle):
    text(draw, (84, 115), "OPENCLAW   /   CEREBRAS", 27, ACCENT, True)
    text(draw, (84, 252), "Santa’s Speedy", 91, bold=True)
    text(draw, (84, 366), "Shopper", 91, bold=True)
    text(draw, (90, 539), subtitle, 35, MUTED)
    text(draw, (90, 696), "Kimi K3.1 Pro  ·  Five Christmas gifts from live retail sites", 28, MUTED)


def score(draw):
    text(draw, (84, 122), "Official Cerebras speed patch", 37, bold=True)
    text(draw, (79, 212), "535", 185, ACCENT, True)
    text(draw, (90, 429), "mean tokens/sec", 52, bold=True)
    text(draw, (90, 523), "577 p90  ·  2 model calls  ·  5 verified retailer links", 31, MUTED)
    text(draw, (90, 684), "Server decoding score. The run also included provider queue retries.", 26, MUTED)


def bars(draw):
    text(draw, (84, 120), "Eight tool steps to one", 58, bold=True)
    text(draw, (88, 209), "Same prompt and Cerebras model in regular OpenClaw", 31, MUTED)
    text(draw, (450, 297), "Tool steps", 24, MUTED)
    text(draw, (1090, 297), "Observed turn time", 24, MUTED)
    for name, count, elapsed, color, y in [
        ("Earlier workflow", 8, "68.2 s", EARLIER, 369),
        ("Optimized shopper", 1, "5.9 s", ACCENT, 496),
    ]:
        text(draw, (89, y + 7), name, 34, bold=True)
        draw.rounded_rectangle((450, y + 4, 990, y + 42), radius=8, fill="#273338")
        draw.rounded_rectangle((450, y + 4, 450 + round(540 * count / 8), y + 42), radius=8, fill=color)
        text(draw, (1016, y + 7), str(count), 34, color, True)
        text(draw, (1091, y + 7), elapsed, 34, bold=True)
    text(draw, (88, 676), "Example runs. Cerebras queue retries varied between runs.", 26, MUTED)


def video(command):
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *command],
        check=True,
    )


def normalize(source):
    source = ROOT / source
    output = WORK / f"cfr-{Path(source).stem}.mp4"
    if not output.exists():
        video([
            "-i", str(source), "-vf", "fps=30,tpad=stop_mode=clone:stop_duration=0.15",
            "-an", "-c:v", "libx264", "-crf", "14", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", str(output),
        ])
    return output


ENCODE = [
    "-an", "-c:v", "libx264", "-crf", "17", "-preset", "fast",
    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
]


def still(name, seconds, painter):
    source = card(name, painter)
    output = WORK / f"{name}.mp4"
    video([
        "-loop", "1", "-framerate", "30", "-i", str(source), "-t", str(seconds),
        *ENCODE, str(output),
    ])
    return output


OPENING = ("fps=30,scale=1312:738:flags=lanczos,"
           "pad=1440:810:64:58:color=0x111619")
CHAT = ("fps=30,crop=900:474:475:40,scale=1260:664:flags=lanczos,"
        "pad=1440:810:90:85:color=0x111619")
PROOF = (
    "[0:v]fps=30,split=2[chat][footer];"
    "[chat]crop=910:382:440:57,scale=1274:534:flags=lanczos,"
    "pad=1440:810:83:66:color=0x111619[page];"
    "[footer]crop=794:116:453:679,scale=1190:174:flags=lanczos[score];"
    "[page][score]overlay=125:622[screen]"
)
LIVE = ("fps=30,drawbox=x=354:y=296:w=123:h=35:color=0x16161a:t=fill:"
        "enable='between(t,0,3.15)',crop=1280:684:80:0,"
        "pad=1440:810:80:68:color=0x111619")
LIVE_ANSWER = ("fps=30,crop=1096:560:120:40,scale=1316:672:flags=lanczos,"
               "pad=1440:810:62:75:color=0x111619")


def footage(name, source, start, seconds, left, right, framing):
    source = normalize(source)
    banner = header(name, left, right)
    output = WORK / f"{name}.mp4"
    screen = framing if framing.startswith("[0:v]") else f"[0:v]{framing}[screen]"
    video([
        "-ss", str(start), "-i", str(source), "-i", str(banner),
        "-filter_complex", f"{screen};[screen][1:v]overlay=0:0[out]",
        "-map", "[out]", "-t", str(seconds), *ENCODE, str(output),
    ])
    return output


def join(name, parts):
    for part in parts:
        if part.stat().st_size < 1024:
            raise ValueError(f"Video segment has no usable frames: {part.name}")
    manifest = WORK / f"{name}-concat.txt"
    manifest.write_text("".join(f"file '{part.name}'\n" for part in parts))
    video([
        "-f", "concat", "-safe", "0", "-i", str(manifest), "-c", "copy",
        "-movflags", "+faststart", str(ROOT / f"{name}.mp4"),
    ])


def bounty(source):
    join(
        "santa-speed-bounty",
        [
            still("bounty-title", 3.2, lambda draw: intro(draw, "Official speed bounty demo")),
            footage(
                "bounty-opening", source, 0.73, 3.4, "Opening the local dashboard",
                "Warm tab · first paint in 0.23 s", OPENING,
            ),
            footage(
                "bounty-proof", source, 2.5, 6.4, "Scored run replay",
                "Five direct product links", PROOF,
            ),
            still("bounty-score", 5.0, score),
        ],
    )


def public_run(replay, live=None):
    parts = [still("public-title", 3.2, lambda draw: intro(draw, "Five gifts in one batch of searches"))]
    if live:
        path = live["path"]
        state = live["state"]
        timing = state.get("shotReadyMs")
        source_duration = live["duration"]
        parts.append(footage(
            "public-live", path, 0.0, min(source_duration, 5.5), "Starting a live run",
            "Regular OpenClaw", LIVE,
        ))
        if timing and len(state.get("links", [])) >= 5:
            answer_start = max(5.5, (timing + state["sendOffsetMs"]) / 1000 - 1.55)
            parts.append(footage(
                "public-live-answer", path, answer_start, source_duration - answer_start,
                "Live answer · queue wait shortened",
                f"{timing / 1000:.1f} s from submit to five links",
                LIVE_ANSWER,
            ))
        if product := live.get("product"):
            parts.append(footage(
                "public-product", product["path"], 0.0, min(product["duration"], 6.2),
                "Opening a returned product page", "REI Co-op", OPENING,
            ))
    parts.extend([
        footage(
            "public-earlier", replay, 0.85, 3.8, "Earlier run replay",
            "8 tool steps · 68.2 s", CHAT,
        ),
        footage(
            "public-optimized", replay, 5.85, 4.3, "Optimized run replay",
            "1 tool step · 5.9 s", CHAT,
        ),
        still("public-chart", 6.2, bars),
    ])
    join("santa-shopper-comparison", parts)


if __name__ == "__main__":
    if sys.argv[1] == "bounty":
        bounty(sys.argv[2])
    else:
        public_run(sys.argv[2], json.loads(Path(sys.argv[3]).read_text()) if len(sys.argv) > 3 else None)
