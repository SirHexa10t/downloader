#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

exec ./build_collages.py \
    --prefix race_bonus \
    --stat "Race Bonus" \
    --unique-pattern "Increases stat gain from races" \
    --buckets 15 10 \
    "$@"
