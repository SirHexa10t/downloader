#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# The "Training Effectiveness" stat is named "Increased Training" in the
# gametora data. The ".*up to" patterns grab the maximum of scaling uniques
# (per-line, the largest matched value wins).
exec ./build_collages.py \
    --prefix training_effectiveness \
    --stat "Increased Training" \
    --unique-pattern "Increases the effectiveness of training performed together" \
    --conditional-pattern "Training Effectiveness" \
    --conditional-pattern "Training Effectiveness.*up to" \
    --conditional-pattern "Increased Training" \
    --conditional-pattern "Increased Training.*up to" \
    --conditional-pattern "0 Energy to" \
    --conditional-pattern "you'll gain \(up to (\d+)\)" \
    --buckets auto --min-total 15 \
    "$@"
