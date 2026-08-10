#!/usr/bin/env python3
"""Filter scraped support cards by a bonus, report totals, build collage grids.

A card's total for a bonus is the sum of:
  - its stat line value, e.g. "Race Bonus: 10"       (--stat)
  - a percentage in its Unique Effect text, matched  (--unique-pattern)
    as <pattern> followed by "(NN%)"

Each requested bucket (--buckets 15 10, or "auto" for every total seen)
becomes one <prefix>_<total>_grid.png in the current directory. The per-filter
entry points (RACE_BONUS.sh, ...) are thin wrappers around this script.
"""

import argparse
import math
import os
import re
import shutil
import sys
from pathlib import Path

from PIL import Image


# ---------------------------
# Reading the scraped .txt files
# ---------------------------

def parse_card_txt(path):
    """-> (stats dict, unique-effect text lines) for one scraped card."""
    stats = {}
    unique_lines = []
    in_unique = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "Unique Effect":
            in_unique = True
        elif line.startswith("    "):
            if in_unique:
                unique_lines.append(line.strip())
        else:
            in_unique = False
            name, sep, value = line.partition(":")
            value = value.strip()
            if sep and value.lstrip("-").isdigit():
                stats[name.strip()] = int(value)
    return stats, unique_lines


def unique_value(unique_lines, patterns, conditional_patterns=()):
    """Bonus granted by the unique effect: (value, conditional lines counted).

    Each unique-effect line contributes the largest value among matching
    patterns. A pattern is normally matched followed by "(N)" or "(N%)" on
    its line; a pattern containing its own capture group is used verbatim
    instead, and the group must capture the number. Lines whose value came
    from a conditional pattern are returned so the report can show what the
    bonus depends on.
    """
    tagged = []
    for pattern, is_conditional in ([(p, False) for p in patterns]
                                    + [(p, True) for p in conditional_patterns]):
        rx = re.compile(pattern)
        if not rx.groups:
            rx = re.compile(pattern + r"\s*\((\d+)%?\)")
        tagged.append((rx, is_conditional))

    total = 0
    conditions = []
    for line in unique_lines:
        best = 0
        best_is_conditional = False
        for rx, is_conditional in tagged:
            match = rx.search(line)
            if match and int(match.group(1)) > best:
                best = int(match.group(1))
                best_is_conditional = is_conditional
        total += best
        if best and best_is_conditional:
            conditions.append(line)
    return total, conditions


def collect_cards(outputs_dir, stat, unique_patterns, conditional_patterns=()):
    """Cards with a non-zero total, sorted by total desc then name."""
    cards = []
    for txt in sorted(outputs_dir.glob("*.txt")):
        stats, unique_lines = parse_card_txt(txt)
        stat_val = stats.get(stat, 0)
        uniq_val, conditions = unique_value(unique_lines, unique_patterns,
                                            conditional_patterns)
        if stat_val or uniq_val:
            cards.append({
                "stem": txt.stem,
                "png": txt.with_suffix(".png"),
                "total": stat_val + uniq_val,
                "stat": stat_val,
                "unique": uniq_val,
                "conditions": conditions,
            })
    return sorted(cards, key=lambda c: (-c["total"], c["stem"]))


def format_row(card):
    row = (f"{card['stem']:<55}  {card['total']:>3}  "
           f"(unique={card['unique']}, mlb_stat={card['stat']})")
    for line in card["conditions"]:
        row += f"  [unique-condition: {line}]"
    return row


# ---------------------------
# Collage grid
# ---------------------------

# the game's own type order, matching the utx_ico_obtain_00..06 icon numbering
TYPE_ORDER = ["SPEED", "STAMINA", "POWER", "GUTS", "WIT", "PAL", "GROUP"]


def card_type_of(path):
    """Type token from a scraped filename like 30010-fine-motion_WIT.png."""
    slug, _, card_type = path.stem.rpartition("_")
    return card_type if slug else ""


def grid_sort_key(path):
    """Type in game order, then rarity (SSR, SR, R), then card id."""
    card_type = card_type_of(path)
    type_rank = (TYPE_ORDER.index(card_type) if card_type in TYPE_ORDER
                 else len(TYPE_ORDER))
    card_id = path.stem.split("-", 1)[0]
    if card_id.isdigit():
        # gametora ids encode rarity in the 10000s: 3xxxx SSR, 2xxxx SR, 1xxxx R
        return (type_rank, 0, -(int(card_id) // 10000), int(card_id), "")
    return (type_rank, 1, 0, 0, path.name)


def load_icons(icon_dir, icon_size):
    icons = {}
    if icon_dir.is_dir():
        for path in sorted(icon_dir.iterdir()):
            if path.suffix.lower() == ".png":
                icon = Image.open(path).convert("RGBA")
                icons[path.stem] = icon.resize((icon_size, icon_size))
    return icons


def build_grid(png_paths, icon_dir, out_path):
    """Square-ish grid of the cards, ordered by grid_sort_key, with the
    card's type icon overlaid top-right when the icons dir provides it."""
    ordered = sorted(png_paths, key=grid_sort_key)
    images = {p.name: Image.open(p).convert("RGBA") for p in ordered}

    tile = images[ordered[0].name].size[0]
    icon_size = tile // 3
    icons = load_icons(icon_dir, icon_size)

    cols = math.ceil(math.sqrt(len(ordered)))
    rows = math.ceil(len(ordered) / cols)

    grid = Image.new("RGBA", (cols * tile, rows * tile), (0, 0, 0, 0))
    for i, path in enumerate(ordered):
        r, c = divmod(i, cols)
        x, y = c * tile, r * tile
        grid.paste(images[path.name], (x, y))
        icon = icons.get(card_type_of(path))
        if icon:
            grid.paste(icon, (x + tile - icon_size, y), icon)

    grid.save(out_path)
    print(f"{len(ordered)} images -> {cols}x{rows} grid "
          f"({cols * tile}x{rows * tile}px) -> {out_path}")


# ---------------------------
# Main
# ---------------------------

def build_bucket(cards, total, prefix, icon_dir, make_folder):
    members = [c for c in cards if c["total"] == total]
    missing = [c["stem"] for c in members if not c["png"].exists()]
    for stem in missing:
        print(f"warning: {stem} has no .png, left out of the {total} grid")
    pngs = [c["png"] for c in members if c["png"].exists()]
    if not pngs:
        print(f"warning: no cards with total {total}, skipping")
        return

    if make_folder:
        folder = Path(f"{prefix}_{total}")
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir()
        for png in pngs:
            shutil.copy2(png, folder / png.name)

    build_grid(pngs, icon_dir, Path(f"{prefix}_{total}_grid.png"))


def main():
    parser = argparse.ArgumentParser(
        description="Filter scraped supports by a bonus and build collage grids."
    )
    parser.add_argument("--stat", required=True,
                        help='stat line to sum, e.g. "Race Bonus"')
    parser.add_argument("--unique-pattern", action="append", default=[],
                        help="unique-effect text granting the bonus, followed by "
                             '"(N)" or "(N%%)" in the card text, e.g. "Increases '
                             'stat gain from races"; may be given multiple times. '
                             "A pattern with its own capture group is used "
                             "verbatim, the group capturing the number")
    parser.add_argument("--conditional-pattern", action="append", default=[],
                        help="like --unique-pattern but for grants with a condition "
                             '(e.g. "Gain Friendship Bonus" ... when the bond gauge '
                             "is full); counted the same, and the report shows the "
                             "matched line")
    parser.add_argument("--buckets", nargs="+", default=[],
                        help='totals to build grids for, e.g. "15 10", '
                             'or "auto" for every total seen')
    parser.add_argument("--prefix", required=True,
                        help="output name prefix, e.g. race_bonus")
    parser.add_argument("--outputs-dir", default="../outputs", type=Path,
                        help="scraped data directory (default: ../outputs)")
    parser.add_argument("--min-total", default=1, type=int,
                        help="ignore auto buckets below this total (default: 1)")
    parser.add_argument("--folders", action="store_true",
                        help="also copy each bucket's cards into <prefix>_<total>/")
    parser.add_argument("--list", action="store_true",
                        help="only print the report, build nothing")
    args = parser.parse_args()

    if not args.outputs_dir.is_dir():
        sys.exit(f"outputs directory not found: {args.outputs_dir}")

    cards = collect_cards(args.outputs_dir, args.stat,
                          args.unique_pattern, args.conditional_pattern)
    for c in cards:
        print(format_row(c))
    if not cards:
        print(f"no cards with any {args.stat!r} found")
        return

    if args.list or not args.buckets:
        return

    if args.buckets == ["auto"]:
        buckets = sorted({c["total"] for c in cards if c["total"] >= args.min_total},
                         reverse=True)
    else:
        buckets = [int(b) for b in args.buckets]

    icon_dir = Path(__file__).resolve().parent / "icons"
    print()
    for total in buckets:
        build_bucket(cards, total, args.prefix, icon_dir, args.folders)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:  # report piped into head/less that exited early
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(0)
