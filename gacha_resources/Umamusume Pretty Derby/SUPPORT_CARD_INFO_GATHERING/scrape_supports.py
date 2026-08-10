#!/usr/bin/env python3
"""Scrape every support card listed in a saved gametora supports page.

Usage: scrape_supports.py <supports_page.html> <stat_table.json>

Acquiring the two inputs (manual):
  1a - save the gametora page ( https://gametora.com/umamusume/supports )
       into a local html file. Make sure the page loaded all relevant supports.
  1b - find in the gametora website the stat-naming json mapping and save it
       (inspect -> sources -> right-click top file -> "Search in all files",
       then look for its fields, like "name_en_eon").

Writes outputs/<card>_<TYPE>.txt and .png for each card. Re-running is safe:
cards whose .txt and .png both already exist are skipped, so an interrupted
run continues where it left off. Use --force to re-download everything
(e.g. after the game data has been updated).

Afterwards, build the collages: filtered_results/RACE_BONUS.sh etc.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://gametora.com"

TYPE_MAP = {
    "utx_ico_obtain_00.png": "SPEED",
    "utx_ico_obtain_01.png": "STAMINA",
    "utx_ico_obtain_02.png": "POWER",
    "utx_ico_obtain_03.png": "GUTS",
    "utx_ico_obtain_04.png": "WIT",
    "utx_ico_obtain_05.png": "PAL",
    "utx_ico_obtain_06.png": "GROUP",
}

# every filename suffix scrape_card() can produce, used by the resume check
TYPE_SUFFIXES = ["_" + t for t in TYPE_MAP.values()] + ["_", ""]

REQUEST_TIMEOUT = 30
RETRIES = 3
RETRY_WAIT = 5


# ---------------------------
# Local parsing (cheap, redone every run)
# ---------------------------

def build_effect_names(stat_table_path):
    """id -> English effect name, preferring the EoN translation."""
    entries = json.loads(Path(stat_table_path).read_text(encoding="utf-8"))
    names = {}
    for entry in entries:
        name = entry.get("name_en_eon") or entry.get("name_en")
        if name:
            names[entry["id"]] = name
    return names


def extract_support_links(html_path):
    """Sorted (page_url, img_url) pairs from a saved supports listing page."""
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    results = {}
    for box in soup.select('a[href^="/umamusume/supports/"]'):
        href = box.get("href")
        if not href or href == "/umamusume/supports":
            continue
        img = box.select_one('img[src^="/images/umamusume/supports/support_card_s_"]')
        img_url = urljoin(BASE, img["src"]) if img else ""
        results[urljoin(BASE, href)] = img_url

    return sorted(results.items())


# ---------------------------
# Card page parsing
# ---------------------------

def final_value(row):
    """Max levelled value of an effect row; -1 marks locked levels."""
    return max(v for v in row[1:] if v != -1)


def parse_unique_effect(soup):
    """The 'Unique Effect' block as indented text lines, [] if the card has none."""
    # class names carry a css-module hash that changes when gametora rebuilds,
    # so match on the stable prefix instead of the full name
    lines = []
    for box in soup.select('div[class*="supports_infobox_effect__"]'):
        caption = box.select_one('div[class*="supports_infobox_effect_text_caption__"]')
        if not caption or "Unique Effect" not in caption.text:
            continue
        lines.append("Unique Effect")
        text = box.select_one('div[class*="supports_infobox_effect_text__"]')
        if text:
            for d in text.find_all("div", recursive=False):
                lines.append(f"    {d.text.strip()}")
        break
    return lines


def parse_card_type(soup):
    """Filename suffix for the card's training type, e.g. '_SPEED'."""
    img = soup.select_one('img[src*="utx_ico_obtain_"]')
    if not img:
        return ""
    filename = img.get("src", "").split("/")[-1]
    return "_" + TYPE_MAP.get(filename, "")


# ---------------------------
# Download
# ---------------------------

def fetch(session, url):
    """GET with retries; raises on persistent failure."""
    for attempt in range(1, RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.RequestException:
            if attempt == RETRIES:
                raise
            time.sleep(RETRY_WAIT * attempt)


def write_atomic(path, data):
    """Write via a temp file + rename, so an existing file implies a complete one."""
    tmp = path.with_name(path.name + ".tmp")
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(tmp, mode) as f:
        f.write(data)
    tmp.replace(path)


def page_name_of(page_url):
    return page_url.rstrip("/").split("/")[-1]


def is_done(outdir, page_name):
    """True if some earlier run already saved both the .txt and the .png."""
    for suffix in TYPE_SUFFIXES:
        txt = outdir / f"{page_name}{suffix}.txt"
        if txt.exists() and txt.with_suffix(".png").exists():
            return True
    return False


def scrape_card(session, page_url, img_url, effect_names, outdir):
    """Fetch one card's page, data json and image; write <slug><type>.txt/.png."""
    page_name = page_name_of(page_url)

    html = fetch(session, page_url).text
    match = re.search(r'"buildId":"([^"]+)"', html)
    if not match:
        raise RuntimeError("no buildId in page HTML")
    build_id = match.group(1)

    json_url = f"{BASE}/_next/data/{build_id}/umamusume/supports/{page_name}.json"
    item = fetch(session, json_url).json()["pageProps"]["itemData"]

    soup = BeautifulSoup(html, "html.parser")
    lines = parse_unique_effect(soup)
    for row in item["effects"]:
        name = effect_names.get(row[0], f"Unknown Effect ({row[0]})")
        lines.append(f"{name}: {final_value(row)}")

    if not img_url:
        raise RuntimeError("no image url in listing")
    image = fetch(session, img_url).content

    txt = outdir / f"{page_name}{parse_card_type(soup)}.txt"
    write_atomic(txt, "\n".join(lines))
    write_atomic(txt.with_suffix(".png"), image)
    return bool(lines and lines[0] == "Unique Effect")


# ---------------------------
# Main
# ---------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Scrape all support cards from a saved gametora supports page."
    )
    parser.add_argument("supports_html", help="saved gametora.com/umamusume/supports page")
    parser.add_argument("stat_table", help="stat-naming json saved from the site sources")
    parser.add_argument("--outdir", default="outputs", type=Path,
                        help="output directory (default: outputs)")
    parser.add_argument("--delay", default=0.2, type=float,
                        help="seconds to sleep between cards (default: 0.2)")
    parser.add_argument("--limit", type=int,
                        help="stop after scraping this many cards (for testing)")
    parser.add_argument("--force", action="store_true",
                        help="re-download cards whose outputs already exist")
    args = parser.parse_args()

    effect_names = build_effect_names(args.stat_table)
    links = extract_support_links(args.supports_html)
    print(f"{len(links)} support cards listed, {len(effect_names)} effect names loaded")

    args.outdir.mkdir(parents=True, exist_ok=True)

    if args.force:
        todo = links
    else:
        todo = [(p, i) for p, i in links if not is_done(args.outdir, page_name_of(p))]
        if len(todo) < len(links):
            print(f"resuming: {len(links) - len(todo)} cards already complete, "
                  f"{len(todo)} to go")
    if args.limit is not None:
        todo = todo[:args.limit]

    session = requests.Session()
    failures = []
    uniques_seen = 0

    for n, (page_url, img_url) in enumerate(todo, 1):
        page_name = page_name_of(page_url)
        print(f"[{n}/{len(todo)}] {page_name} ... ", end="", flush=True)
        try:
            uniques_seen += scrape_card(session, page_url, img_url,
                                        effect_names, args.outdir)
            print("ok")
        except Exception as e:
            failures.append((page_name, e))
            print(f"FAILED ({e})")
        if args.delay and n < len(todo):
            time.sleep(args.delay)

    print(f"\ndone: {len(todo) - len(failures)} scraped, {len(failures)} failed")
    if len(todo) - len(failures) >= 20 and uniques_seen == 0:
        print("warning: no card had a Unique Effect block - "
              "the page structure may have changed")
    if failures:
        for page_name, e in failures:
            print(f"  failed: {page_name}: {e}")
        print("re-run the same command to retry just the failed cards")
        sys.exit(1)


if __name__ == "__main__":
    main()
