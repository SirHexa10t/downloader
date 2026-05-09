#!/usr/bin/env python3

import sys
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://gametora.com"
OUTPUT_FILE = "support_links.txt"


def extract_links(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    results_dict = {}

    for box in soup.select('a[href^="/umamusume/supports/"]'):
        page_href = box.get("href")
        if not page_href or page_href == "/umamusume/supports":
            continue

        page_url = urljoin(BASE, page_href)

        # Find the image inside the box
        img_tag = box.select_one('img[src^="/images/umamusume/supports/support_card_s_"]')
        if img_tag:
            img_url = urljoin(BASE, img_tag["src"])
        else:
            img_url = ""

        # Save to dict, automatically overwriting duplicates
        results_dict[page_url] = img_url

    # Convert to sorted list of strings: "page_url img_url"
    sorted_results = [f"{url} {results_dict[url]}" for url in sorted(results_dict.keys())]

    return sorted_results


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <html_file>")
        sys.exit(1)

    html_file = sys.argv[1]

    links = extract_links(html_file)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for link in links:
            f.write(link + "\n")

    print(f"Extracted {len(links)} links → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
