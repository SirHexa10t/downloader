#!/usr/bin/env python3
"""Scrape comics from the old Lunarbaboon Squarespace site."""

import html as htmlmod
import os
import re
import time
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "http://www.lunarbaboon.com/comics/"
FIRST_PAGE = 1
LAST_PAGE = 196
OUTPUT_DIR = "lunarbaboon_old"
SITE_ORIGIN = "http://www.lunarbaboon.com"
REQUEST_DELAY = 1.0

# Within an entry: title, date, image URL
TITLE_RE = re.compile(
    r'<a class="journal-entry-navigation-current"[^>]*>([^<]+)</a>'
)
DATE_RE = re.compile(
    r'<span class="posted-on">.*?([A-Z][a-z]+day,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\s+at\s+\d{1,2}:\d{2}[AP]M)',
    re.DOTALL,
)
IMAGE_RE = re.compile(
    r'<div class="body">.*?<img[^>]+src="([^"]+)"',
    re.DOTALL,
)
# Trailing number in the image filename, e.g. "Comicappreciation145.jpg"
IMG_NUM_RE = re.compile(r'(\d+)\.\w+(?:\?|$)')


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse_date(raw: str) -> str:
    """'Monday, July 23, 2012 at 07:49AM' → '2012-07-23'"""
    dt = datetime.strptime(raw.strip(), "%A, %B %d, %Y at %I:%M%p")
    return dt.strftime("%Y-%m-%d")


def parse_entries(page_html: str) -> list[dict]:
    """Extract comic entries from one listing page."""
    # Split on entry wrappers — more robust than a single regex across nested divs
    parts = re.split(r'(?=<div class="journal-entry-wrapper)', page_html)
    entries = []

    for block in parts:
        if not block.startswith('<div class="journal-entry-wrapper'):
            continue

        title_m = TITLE_RE.search(block)
        date_m = DATE_RE.search(block)
        img_m = IMAGE_RE.search(block)
        if not (title_m and date_m and img_m):
            continue

        title = htmlmod.unescape(title_m.group(1).strip())
        date_str = parse_date(date_m.group(1))
        img_url = img_m.group(1)
        if img_url.startswith("//"):
            img_url = "http:" + img_url
        elif img_url.startswith("/"):
            img_url = SITE_ORIGIN + img_url
        img_url = img_url.replace(" ", "%20")

        # Extract the number from the original image filename
        filename = img_url.split("/")[-1]
        num_m = IMG_NUM_RE.search(filename)
        num = num_m.group(1) if num_m else ""

        # Original extension
        ext_m = re.search(r'\.(\w+)(?:\?|$)', filename)
        ext = ext_m.group(1).lower() if ext_m else "jpg"

        # e.g. 2012-07-23_APPRECIATION145.jpg
        safe_title = re.sub(r'[^\w]+', '-', title).strip('-').upper()
        out_name = f"{date_str}_{safe_title}{num}.{ext}"

        entries.append({
            "title": title,
            "date": date_str,
            "img_url": img_url,
            "out_name": out_name,
        })
    return entries


def download_image(url: str, out_path: str) -> bool:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            return True
    except Exception as exc:
        print(f"    ✗ Failed: {exc}")
        return False


def scrape() -> None:
    """Walk all listing pages, extract comic entries, download images."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for page_num in range(FIRST_PAGE, LAST_PAGE + 1):
        # http://www.lunarbaboon.com/comics/
        # http://www.lunarbaboon.com/comics/?currentPage=2
        # ...
        # http://www.lunarbaboon.com/comics/?currentPage=196
        url = BASE_URL if page_num == 1 else f"{BASE_URL}?currentPage={page_num}"
        print(f"[{page_num}/{LAST_PAGE}] {url}")

        try:
            html = fetch_page(url)
        except Exception as exc:
            print(f"  ⚠ Failed to fetch page: {exc}")
            continue

        entries = parse_entries(html)
        if not entries:
            print("  No entries found.")

        for entry in entries:
            out_path = os.path.join(OUTPUT_DIR, entry["out_name"])
            if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                print(f"  {entry['out_name']} — exists, skipping.")
                continue

            print(f"  {entry['out_name']} — downloading…")
            download_image(entry["img_url"], out_path)
            time.sleep(0.3)

        time.sleep(REQUEST_DELAY)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    scrape()
    