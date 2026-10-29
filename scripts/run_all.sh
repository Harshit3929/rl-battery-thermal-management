#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -n "${PY:-}" ]; then :;
elif [ -x ".venv/Scripts/python.exe" ]; then PY=".venv/Scripts/python.exe";
elif [ -x ".venv/bin/python" ]; then PY=".venv/bin/python";
else PY="python"; fi
STEPS="${STEPS:-20000}"
WORKERS="${WORKERS:-8}"
"$PY" -m btms.analysis.hardness
"$PY" -m btms.analysis.evaluate controller=pid --tune
for controller in null bangbang pid mpc; do
  "$PY" -m btms.analysis.evaluate controller="$controller"
  "$PY" -m btms.analysis.evaluate controller="$controller" --no-shield
done
for agent in sac td3 ppo; do
  for seed in 0 1 2 3 4; do
    "$PY" -m btms.train agent="$agent" scenario=mixed seed="$seed" total_steps="$STEPS" n_envs="$WORKERS" log.dir="outputs/study_$STEPS"
  done
done
"$PY" -m btms.analysis.aggregate --root "outputs/study_$STEPS" --out report/results
