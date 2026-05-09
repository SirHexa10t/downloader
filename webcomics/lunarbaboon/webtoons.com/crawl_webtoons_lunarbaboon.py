#!/usr/bin/env python3
"""Crawl Webtoons Lunarbaboon: discover episode links, download comic images."""

import os
import re
import time
import urllib.request

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = "https://www.webtoons.com/en/slice-of-life/lunarbaboon/list?title_no=523"
FIRST_PAGE = 1
LAST_PAGE = 75
LINKS_FILE = "lunarbaboon_links.txt"
IMAGES_DIR = "lunarbaboon_panels"
FINAL_DIR = "lunarbaboon_finalized"
PANEL_GAP = 20            # pixels of white space between panels
MAX_MERGE = 0             # limit for testing; set to >0 to cap
MAX_RETRIES = 5           # max validation+retry passes after initial download
REDOWNLOAD_LAST = False   # set True to re-download the last existing folder
REQUEST_DELAY = 1.0       # seconds between requests, be polite

EPISODE_LINK_RE = re.compile(
    r'<a\s+href="(https://www\.webtoons\.com/en/slice-of-life/lunarbaboon/[^"]+/viewer\?title_no=523&episode_no=\d+)"'
)
IMAGE_RE = re.compile(
    r'<img\s[^>]*class="_images"[^>]*data-url="([^"]+)"',
)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------
def fetch_page(url: str) -> str:
    """Download a single page and return its HTML as a string."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def discover_episode_links() -> list[str]:
    """Walk every listing page and return a deduplicated, sorted list of episode URLs."""
    seen: set[str] = set()
    all_links: list[str] = []

    for page_num in range(FIRST_PAGE, LAST_PAGE + 1):
        # Listing pages look like:
        #   https://www.webtoons.com/en/slice-of-life/lunarbaboon/list?title_no=523
        #   https://www.webtoons.com/en/slice-of-life/lunarbaboon/list?title_no=523&page=2
        #   ...
        #   https://www.webtoons.com/en/slice-of-life/lunarbaboon/list?title_no=523&page=75
        url = BASE_URL if page_num == 1 else f"{BASE_URL}&page={page_num}"
        print(f"[{page_num}/{LAST_PAGE}] Fetching {url}")

        try:
            html = fetch_page(url)
        except Exception as exc:
            print(f"  ⚠ Failed: {exc}")
            continue

        links = EPISODE_LINK_RE.findall(html)
        new = 0
        for link in links:
            if link not in seen:
                seen.add(link)
                all_links.append(link)
                new += 1
        print(f"  Found {len(links)} link(s), {new} new")

        if page_num < LAST_PAGE:
            time.sleep(REQUEST_DELAY)

    # Sort by episode number so the file is in a natural order
    def episode_number(url: str) -> int:
        m = re.search(r"episode_no=(\d+)", url)
        return int(m.group(1)) if m else 0

    all_links.sort(key=episode_number)
    return all_links


def save_links() -> None:
    """Discover episode links and write them to LINKS_FILE, one per line.

    Skips the crawl if the file already exists and is non-empty.
    """
    if os.path.isfile(LINKS_FILE) and os.path.getsize(LINKS_FILE) > 0:
        print(f"{LINKS_FILE} already exists and is non-empty, skipping download.")
        return

    print(f"{LINKS_FILE} missing or empty, discovering episode links…")
    links = discover_episode_links()
    with open(LINKS_FILE, "w") as f:
        for link in links:
            f.write(link + "\n")
    print(f"\nSaved {len(links)} episode link(s) to {LINKS_FILE}")


def load_links() -> list[str]:
    """Read episode URLs from LINKS_FILE.

    Each line is a viewer URL like:
      https://www.webtoons.com/en/slice-of-life/lunarbaboon/ep-6-partners/viewer?title_no=523&episode_no=6
    """
    with open(LINKS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]


def episode_name(url: str) -> str:
    """Extract the short name from an episode URL.

    e.g. '.../ep-6-partners/viewer?...' → 'ep-6-partners'
    """
    # The name sits between the last two '/' before '/viewer'
    path = url.split("?")[0]          # drop query string
    parts = path.rstrip("/").split("/")
    # …/lunarbaboon/ep-6-partners/viewer → parts[-2]
    return parts[-2]


def download_image(img_url: str, referer: str, out_path: str) -> bool:
    """Download a single image with the episode page as Referer."""
    headers = {"User-Agent": "Mozilla/5.0", "Referer": referer}
    req = urllib.request.Request(img_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            return True
    except Exception as exc:
        print(f"    ✗ Failed to download {out_path}: {exc}")
        return False


def download_episode_panels(episode_url: str, dest_dir: str) -> int:
    """Fetch one episode page, extract panel image URLs (skip the first
    title image), and download them into *dest_dir*.

    Returns the number of panels saved.
    """
    html = fetch_page(episode_url)
    img_urls = IMAGE_RE.findall(html)

    # Skip index 0 — it's the comic title banner, not a panel
    panels = img_urls[1:]
    if not panels:
        print(f"    ⚠ No panel images found")
        return 0

    os.makedirs(dest_dir, exist_ok=True)
    saved = 0
    for i, url in enumerate(panels):
        ext = ".png" if ".png" in url.lower() else ".jpg"
        out_path = os.path.join(dest_dir, f"{i + 1:02d}{ext}")
        if download_image(url, referer=episode_url, out_path=out_path):
            saved += 1
        time.sleep(0.2)  # small delay between image downloads

    return saved


def _find_missing(links: list[str]) -> list[tuple[int, str, str]]:
    """Return a list of (index, name, url) for episodes with missing or empty folders."""
    missing = []
    for i, url in enumerate(links):
        name = episode_name(url)
        folder = os.path.join(IMAGES_DIR, name)
        if not os.path.isdir(folder) or not os.listdir(folder):
            missing.append((i, name, url))
    return missing


def save_images() -> None:
    """Download panel images for every episode into per-episode folders.

    Skips episodes whose folder already exists and contains files.
    If REDOWNLOAD_LAST is True, the last existing folder gets re-downloaded
    in case a previous run was interrupted mid-episode.

    After the download pass, runs a full validation scan. If any episodes
    are still missing (e.g. due to mid-run denial), retries them in a loop
    until everything is present or no progress is being made.
    """
    import shutil

    links = load_links()
    total = len(links)
    print(f"\n{total} episode(s) to process.")

    # --- Initial download pass ---------------------------------------------
    last_existing_idx = -1
    for i, url in enumerate(links):
        dest_dir = os.path.join(IMAGES_DIR, episode_name(url))
        if os.path.isdir(dest_dir) and os.listdir(dest_dir):
            last_existing_idx = i

    for idx, url in enumerate(links, 1):
        name = episode_name(url)
        dest_dir = os.path.join(IMAGES_DIR, name)
        is_last_existing = (idx - 1 == last_existing_idx)

        if os.path.isdir(dest_dir) and os.listdir(dest_dir):
            if is_last_existing and REDOWNLOAD_LAST:
                print(f"[{idx}/{total}] {name} — last existing folder, re-downloading (may be incomplete)…")
                shutil.rmtree(dest_dir)
            else:
                if is_last_existing:
                    print(f"[{idx}/{total}] {name} — skipping (set REDOWNLOAD_LAST = True to re-download)")
                else:
                    print(f"[{idx}/{total}] {name} — already downloaded, skipping.")
                continue
        else:
            print(f"[{idx}/{total}] {name} — downloading panels…")

        try:
            saved = download_episode_panels(url, dest_dir)
            print(f"    Saved {saved} panel(s)")
        except Exception as exc:
            print(f"    ✗ Failed: {exc}")

        time.sleep(REQUEST_DELAY)

    # --- Validation + retry loop ------------------------------------------
    missing = _find_missing(links)
    for attempt in range(1, MAX_RETRIES + 1):
        if not missing:
            break

        print(f"\n⚠ {len(missing)} missing episode(s) — retry {attempt}/{MAX_RETRIES}:")
        for _, name, url in missing:
            dest_dir = os.path.join(IMAGES_DIR, name)
            print(f"  Retrying {name}…")
            try:
                saved = download_episode_panels(url, dest_dir)
                print(f"    Saved {saved} panel(s)")
            except Exception as exc:
                print(f"    ✗ Failed: {exc}")
            time.sleep(REQUEST_DELAY)

        missing = _find_missing(links)

    if not missing:
        print(f"\n✓ Full validation passed: all {total} episodes present.")
    else:
        print(f"\n✗ Still {len(missing)} episode(s) missing after {MAX_RETRIES} retries:")
        for _, name, _ in missing:
            print(f"    {name}")
        print("Fix these manually and re-run.")
        raise SystemExit(1)


def verify_panels() -> list[tuple[str, str]]:
    """Check that every episode in LINKS_FILE has a non-empty panel folder.

    Returns a list of (episode_name, folder_path) pairs in link-file order.
    Raises SystemExit if anything is missing or empty.
    """
    links = load_links()
    episodes: list[tuple[str, str]] = []
    problems: list[str] = []

    for url in links:
        name = episode_name(url)
        folder = os.path.join(IMAGES_DIR, name)
        episodes.append((name, folder))

        if not os.path.isdir(folder):
            problems.append(f"  Missing folder: {folder}")
        elif not os.listdir(folder):
            problems.append(f"  Empty folder:   {folder}")

    if problems:
        print(f"Panel verification failed — {len(problems)} problem(s):")
        for p in problems:
            print(p)
        raise SystemExit(1)

    print(f"Panel verification passed: {len(episodes)} episode folder(s), all non-empty.")
    return episodes


def merge_episode(name: str, panel_dir: str, out_path: str) -> None:
    """Join all panel images in *panel_dir* into one tall image with
    PANEL_GAP pixels of white space between them, saved to *out_path*.
    """
    from PIL import Image

    # Sorted so panels stay in the right order (01.png, 02.png, …)
    files = sorted(f for f in os.listdir(panel_dir)
                   if f.lower().endswith((".png", ".jpg", ".jpeg")))

    images = [Image.open(os.path.join(panel_dir, f)).convert("RGBA") for f in files]

    total_width = max(img.width for img in images)
    total_height = sum(img.height for img in images) + PANEL_GAP * (len(images) - 1)

    merged = Image.new("RGBA", (total_width, total_height), color=(255, 255, 255, 255))
    y = 0
    for img in images:
        # Centre narrower panels horizontally
        x = (total_width - img.width) // 2
        merged.paste(img, (x, y), img)
        y += img.height + PANEL_GAP

    merged.convert("RGB").save(out_path, "WEBP", quality=85)
    for img in images:
        img.close()


def merge_comics() -> None:
    """Verify panels, then merge each episode's panels into a single image.

    Output goes to FINAL_DIR as  <episode-name>.webp .
    Skips episodes whose final image already exists.
    """
    episodes = verify_panels()
    os.makedirs(FINAL_DIR, exist_ok=True)

    to_process = episodes
    if MAX_MERGE > 0:
        to_process = episodes[:MAX_MERGE]
        print(f"(Limited to first {MAX_MERGE} episodes for testing.)")

    total = len(to_process)
    for idx, (name, panel_dir) in enumerate(to_process, 1):
        out_path = os.path.join(FINAL_DIR, f"{name}.webp")

        if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            print(f"[{idx}/{total}] {name} — already merged, skipping.")
            continue

        print(f"[{idx}/{total}] {name} — merging…")
        try:
            merge_episode(name, panel_dir, out_path)
            size_kb = os.path.getsize(out_path) / 1024
            print(f"    → {out_path}  ({size_kb:.0f} KB)")
        except Exception as exc:
            print(f"    ✗ Failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    save_links()
    save_images()
    merge_comics()