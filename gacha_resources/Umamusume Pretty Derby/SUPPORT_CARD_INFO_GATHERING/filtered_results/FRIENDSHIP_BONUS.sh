#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

exec ./build_collages.py \
    --prefix friendship_bonus \
    --stat "Friendship Bonus" \
    --unique-pattern "Increases the effectiveness of Friendship Training" \
    --conditional-pattern "Gain Friendship Bonus" \
    --conditional-pattern "up to 5 times for a total of" \
    --buckets auto --min-total 20 \
    "$@"
