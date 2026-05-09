#!/usr/bin/env python3

import json
import sys

# usage: python gen_effect_lookup.py effects.json
with open(sys.argv[1], "r", encoding="utf-8") as f:
    data = json.load(f)

print("effect_names = {")

for entry in data:
    effect_id = entry["id"]

    # prefer the EoN translation, otherwise fall back to normal English
    name = entry.get("name_en_eon") or entry.get("name_en")

    if name:
        print(f"    {effect_id}: {name!r},")

print("}")

