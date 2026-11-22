#!/usr/bin/env bash
# Bounded benchmark series: series.sh <label-prefix> <successes> <attempts> [cooldown_s]
set -u
cd "$(dirname "$(realpath "$0")")/.."
node="${OPENCLAW_BOUNTY_NODE:-$HOME/.local/share/mise/installs/node/26.13.1/bin/node}"
ok=0
for i in $(seq 1 "$3"); do
  if BENCH_LIMIT_MS=45000 timeout 75 "$node" candidate/bench.mjs candidate/candidate-openclaw "$1-$i" >/dev/null 2>&1; then
    ok=$((ok+1)); echo "$1-$i ok"
    [ "$ok" -ge "$2" ] && break
  else echo "$1-$i stalled"; fi
  [ "$i" -lt "$3" ] && sleep "${4:-120}"
done
