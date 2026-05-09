#!/usr/bin/env bash

#!/usr/bin/env bash
set -euo pipefail

DIRECTORY='../outputs/'

unique_bonus="Increases stat gain from races"
mlb_bonus="Race Bonus"

find "$DIRECTORY" -maxdepth 1 -name '*.txt' -type f \
  -exec grep -PH "${unique_bonus}\\s*\\([0-9]+%\\)|${mlb_bonus}:\\s*[0-9]+" {} + \
  2>/dev/null |
awk -v p1_tag="$unique_bonus" -v p2_tag="$mlb_bonus" '
  {
    # split on first colon only to get filename vs matched line
    sep = index($0, ":")
    file = substr($0, 1, sep - 1)
    line = substr($0, sep + 1)

    if (match(line, p1_tag "[[:space:]]*\\(([0-9]+)%", m)) {
      if (!(file in p1)) p1[file] = m[1] + 0
    }
    if (match(line, p2_tag ":[[:space:]]*([0-9]+)", m)) {
      if (!(file in p2)) p2[file] = m[1] + 0
    }
    files[file] = 1
  }
  END {
    for (f in files) {
      total = (p1[f]+0) + (p2[f]+0)  # aggregate, whichever wasnt found is considered 0
      printf "%d\t%s\t%d\t%d\n", total, f, p1[f]+0, p2[f]+0
    }
  }
' | sort -rn -t$'\t' -k1 |
while IFS=$'\t' read -r total file v1 v2; do
  printf '%-60s  %d  (unique=%s, mlb_stat=%s)\n' "$file" "$total" "$v1" "$v2"
done
