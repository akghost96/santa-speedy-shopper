#!/usr/bin/env bash
# Record a live browser video of the native-catalog candidate (gateway 18891).
# Never touches the submission video. Keeps the best verified take as
#   santa-speed-bounty-candidate.mp4   (archived in submissions/candidate-<tps>tps.mp4)
#   .recording-work/record-candidate-video.sh [attempts] [limit_ms] [good_enough_tps]
set -u
cd "$(dirname "$(realpath "$0")")/.."
root="$PWD"; work="$root/.recording-work"
node="${OPENCLAW_BOUNTY_NODE:-$HOME/.local/share/mise/installs/node/26.13.1/bin/node}"
attempts="${1:-10}"; limit="${2:-45000}"; enough="${3:-1300}"
best_file="$work/candidate-video-best.json"
mkdir -p "$work/takes" "$root/submissions" "$root/.benchmarks/candidate"
best=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mean_tps"])' "$best_file" 2>/dev/null || echo 0)

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$work/pw-browsers}"
export SANTA_PORT=18891 SANTA_STATE=.candidate-state SANTA_LAUNCHER=candidate/candidate-openclaw
export SANTA_SCORE_TITLE="Native catalog candidate" SANTA_VIDEO_OUT="santa-speed-bounty-candidate" SANTA_VIDEO_FULL="santa-speed-bounty-candidate-full"

for i in $(seq 1 "$attempts"); do
  id="cvid$(date +%s)t$i"
  export SANTA_CAPTURE_KEY="agent:main:bounty-short-$id"
  "$root/candidate/candidate-openclaw" gateway call sessions.create --json \
    --params "{\"key\":\"$SANTA_CAPTURE_KEY\"}" >/dev/null 2>&1 || { echo "$id: sessions.create failed"; sleep 3; continue; }
  export SANTA_CAPTURE_LIMIT="$limit" SANTA_RAW="raw/$id.webm" \
    SANTA_CAPTURE_JSON="takes/$id.capture.json" SANTA_RESULT_PNG="takes/$id.result.png" \
    SANTA_EDIT_JSON="takes/$id.edit.json" SANTA_HISTORY_OUT=".benchmarks/candidate/video-$id.json"
  if ! timeout $(( limit / 1000 + 60 )) "$node" "$work/capture-timed.mjs" >"$work/takes/$id.capture.log" 2>&1; then
    echo "$id: no complete answer within $((limit / 1000)) s ($(tail -1 "$work/takes/$id.capture.log"))"
    sleep 5; continue
  fi
  if ! (cd "$work" && python3 verify_timed.py) >"$work/takes/$id.verify.log" 2>&1; then
    echo "$id: verification failed ($(tail -1 "$work/takes/$id.verify.log"))"; continue
  fi
  read -r mean p90 secs < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["mean_tps"], d["p90_tps"], d["elapsed_ms"]/1000)' "$work/$SANTA_EDIT_JSON")
  echo "$id: verified take, $mean mean / $p90 p90 TPS, ${secs}s Enter-to-list (best so far $best)"
  if [ "$mean" -gt "$best" ]; then
    (cd "$work" && python3 timed_edit.py ".recording-work/$SANTA_RAW" "$SANTA_EDIT_JSON") >"$work/takes/$id.render.log" 2>&1 \
      || { echo "$id: render failed"; continue; }
    cp "$root/santa-speed-bounty-candidate.mp4" "$root/submissions/candidate-${mean}tps.mp4"
    printf '{"mean_tps": %s, "p90_tps": %s, "elapsed_s": %s, "take": "%s", "file": "santa-speed-bounty-candidate.mp4"}\n' \
      "$mean" "$p90" "$secs" "$id" > "$best_file"
    best=$mean
    echo "$id: NEW CANDIDATE VIDEO santa-speed-bounty-candidate.mp4 ($mean mean TPS)"
  fi
  [ "$best" -ge "$enough" ] && { echo "done: $best >= $enough"; break; }
done
echo "finished: best candidate take $best mean TPS"
