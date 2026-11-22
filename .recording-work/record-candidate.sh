#!/usr/bin/env bash
# Record live browser takes of the candidate shopper (gateway on 18891) and
# update the submission video whenever a verified take beats the TPS shown in
# the current video by at least STEP (default 50).
#   .recording-work/record-candidate.sh <takes> [limit_ms]
# Every take: prompt typed on screen, Enter starts the stopwatch, the fifth
# link stops it, the official per-call server TPS from the same run is shown.
set -u
cd "$(dirname "$(realpath "$0")")/.."
root="$PWD"
work="$root/.recording-work"
node="${OPENCLAW_BOUNTY_NODE:-$HOME/.local/share/mise/installs/node/26.13.1/bin/node}"
takes="${1:-3}"
limit="${2:-28000}"
step="${STEP:-50}"
record="$work/video-record.json"
archive="$root/submissions"
mkdir -p "$work/takes" "$archive" "$root/.benchmarks/candidate"
[ -f "$record" ] || echo '{"mean_tps": 527, "file": "santa-speed-bounty.mp4", "source": "baseline video"}' > "$record"

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$work/pw-browsers}"
export SANTA_PORT=18891 SANTA_STATE=.candidate-state SANTA_LAUNCHER=candidate/candidate-openclaw

for i in $(seq 1 "$takes"); do
  id="cand$(date +%s)t$i"
  export SANTA_CAPTURE_KEY="agent:main:bounty-short-$id"
  # The Control UI only opens session links that already exist on this build.
  "$root/candidate/candidate-openclaw" gateway call sessions.create --json \
    --params "{\"key\":\"$SANTA_CAPTURE_KEY\"}" >/dev/null 2>&1 || { echo "$id: sessions.create failed"; continue; }
  export SANTA_CAPTURE_LIMIT="$limit"
  export SANTA_RAW="raw/$id.webm"
  export SANTA_CAPTURE_JSON="takes/$id.capture.json"
  export SANTA_RESULT_PNG="takes/$id.result.png"
  export SANTA_EDIT_JSON="takes/$id.edit.json"
  export SANTA_HISTORY_OUT=".benchmarks/candidate/video-$id.json"
  if ! timeout $(( limit / 1000 + 60 )) "$node" "$work/capture-timed.mjs"; then
    echo "$id: no complete answer within $((limit / 1000)) s"
    sleep 5
    continue
  fi
  if ! (cd "$work" && python3 verify_timed.py); then
    echo "$id: verification failed"
    continue
  fi
  mean=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mean_tps"])' "$work/$SANTA_EDIT_JSON")
  best=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mean_tps"])' "$record")
  echo "$id: verified take, $mean mean TPS (video shows $best)"
  if [ "$mean" -ge $(( best + step )) ]; then
    (cd "$work" && python3 timed_edit.py ".recording-work/$SANTA_RAW" "$SANTA_EDIT_JSON") || { echo "$id: render failed"; continue; }
    out="$archive/santa-speed-bounty-${mean}tps.mp4"
    cp "$root/santa-speed-bounty-timed-review.mp4" "$out"
    cp "$out" "$root/santa-speed-bounty.mp4"
    python3 - "$record" "$mean" "$out" "$id" <<'PY'
import json, sys, time
path, mean, out, take = sys.argv[1:]
data = json.load(open(path))
history = data.get("history", [])
history.append({"mean_tps": data["mean_tps"], "file": data["file"], "source": data.get("source")})
json.dump({"mean_tps": int(mean), "file": out, "source": take, "updated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "history": history}, open(path, "w"), indent=2)
PY
    echo "$id: NEW VIDEO $out ($best -> $mean)"
  fi
done
