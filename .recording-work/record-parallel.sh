#!/usr/bin/env bash
# Record live browser takes of the native-catalog candidate (gateway 18891) with
# several workers at once, until a wall-clock deadline. Every take is the same
# as record-candidate-video.sh: prompt typed on screen, Enter starts the
# stopwatch, the fifth link stops it, the official server TPS is read from the
# UI and re-checked against chat.history by verify_timed.py.
#
#   .recording-work/record-parallel.sh <workers> <minutes> [limit_ms]
#
# Results: one JSON line per verified take in .recording-work/parallel-results.jsonl.
# A take that beats candidate-video-best.json is rendered (one render at a
# time) to santa-speed-bounty-candidate.mp4 and archived in submissions/.
# Raw recordings below KEEP_TPS (default 1400) are deleted to save disk.
set -u
cd "$(dirname "$(realpath "$0")")/.."
root="$PWD"; work="$root/.recording-work"
node="${OPENCLAW_BOUNTY_NODE:-$HOME/.local/share/mise/installs/node/26.13.1/bin/node}"
workers="${1:-3}"; minutes="${2:-30}"; limit="${3:-30000}"
keep="${KEEP_TPS:-1400}"
deadline=$(( $(date +%s) + minutes * 60 ))
results="$work/parallel-results.jsonl"
best_file="$work/candidate-video-best.json"
lock="$work/.render.lock"
mkdir -p "$work/takes" "$work/raw" "$root/submissions" "$root/.benchmarks/candidate"

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$work/pw-browsers}"
export SANTA_PORT=18891 SANTA_STATE=.candidate-state SANTA_LAUNCHER=candidate/candidate-openclaw
export SANTA_SCORE_TITLE="Native catalog candidate" SANTA_VIDEO_OUT="santa-speed-bounty-candidate" SANTA_VIDEO_FULL="santa-speed-bounty-candidate-full"

worker() {
  local w="$1" i=0
  while [ "$(date +%s)" -lt "$deadline" ] && [ ! -e "$work/.stop-parallel" ]; do
    i=$((i + 1))
    local id="pv$(date +%s)w${w}t$i"
    export SANTA_CAPTURE_KEY="agent:main:bounty-short-$id"
    "$root/candidate/candidate-openclaw" gateway call sessions.create --json \
      --params "{\"key\":\"$SANTA_CAPTURE_KEY\"}" >/dev/null 2>&1 || { echo "$id: sessions.create failed"; sleep 3; continue; }
    export SANTA_CAPTURE_LIMIT="$limit" SANTA_RAW="raw/$id.webm" \
      SANTA_CAPTURE_JSON="takes/$id.capture.json" SANTA_RESULT_PNG="takes/$id.result.png" \
      SANTA_EDIT_JSON="takes/$id.edit.json" SANTA_HISTORY_OUT=".benchmarks/candidate/video-$id.json"
    if ! timeout $(( limit / 1000 + 60 )) "$node" "$work/capture-timed.mjs" >"$work/takes/$id.capture.log" 2>&1; then
      echo "$id: no complete answer within $((limit / 1000)) s"
      rm -f "$work/takes/$id.capture.log"
      sleep 2; continue
    fi
    if ! (cd "$work" && python3 verify_timed.py) >"$work/takes/$id.verify.log" 2>&1; then
      echo "$id: verification failed ($(tail -1 "$work/takes/$id.verify.log"))"
      rm -f "$work/$SANTA_RAW"; continue
    fi
    local mean p90 secs
    read -r mean p90 secs < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d["mean_tps"], d["p90_tps"], d["elapsed_ms"]/1000)' "$work/$SANTA_EDIT_JSON")
    printf '{"id": "%s", "mean_tps": %s, "p90_tps": %s, "elapsed_s": %s, "at": "%s"}\n' "$id" "$mean" "$p90" "$secs" "$(date +%H:%M:%S)" >> "$results"
    echo "$id: verified $mean mean / $p90 p90, ${secs}s"
    if [ "$mean" -lt "$keep" ]; then
      rm -f "$work/$SANTA_RAW" "$work/takes/$id.result.png" "$work/takes/$id.capture.log" "$work/takes/$id.verify.log" "$root/$SANTA_HISTORY_OUT"
      continue
    fi
    # Render under a lock: timed_edit.py uses fixed scratch names.
    (
      flock 9
      best=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["mean_tps"])' "$best_file" 2>/dev/null || echo 0)
      if [ "$mean" -gt "$best" ]; then
        if (cd "$work" && python3 timed_edit.py ".recording-work/$SANTA_RAW" "$SANTA_EDIT_JSON") >"$work/takes/$id.render.log" 2>&1; then
          cp "$root/santa-speed-bounty-candidate.mp4" "$root/submissions/candidate-${mean}tps.mp4"
          printf '{"mean_tps": %s, "p90_tps": %s, "elapsed_s": %s, "take": "%s", "file": "santa-speed-bounty-candidate.mp4"}\n' \
            "$mean" "$p90" "$secs" "$id" > "$best_file"
          echo "$id: NEW CANDIDATE VIDEO ($mean mean / $p90 p90) -> submissions/candidate-${mean}tps.mp4"
        else
          echo "$id: render failed (see takes/$id.render.log)"
        fi
      fi
    ) 9>"$lock"
  done
}

rm -f "$work/.stop-parallel"
for w in $(seq 1 "$workers"); do
  worker "$w" &
  sleep 2
done
wait
echo "finished: best $(cat "$best_file")"
