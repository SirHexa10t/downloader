#!/usr/bin/env python3

import requests
import re
import json
import sys
from pathlib import Path

# Effect lookup
effect_names = {
    1: 'Friendship Bonus',
    2: 'Mood Bonus',
    3: 'Speed Bonus',
    4: 'Stamina Bonus',
    5: 'Power Bonus',
    6: 'Guts Bonus',
    7: 'Wisdom Bonus',
    8: 'Increased Training',
    9: 'Initial Speed Up',
    10: 'Initial Stamina Up',
    11: 'Initial Power Up',
    12: 'Initial Guts Up',
    13: 'Initial Wisdom Up',
    14: 'Starting Bond Up',
    15: 'Race Bonus',
    16: 'Fan Count Bonus',
    17: 'Hint Lv. Bonus',
    18: 'Hint Rate Up',
    19: 'Specialty Rate Up',
    20: 'Speed Limit Up',
    21: 'Stamina Limit Up',
    22: 'Power Limit Up',
    23: 'Guts Limit Up',
    24: 'Intelligence Limit Up',
    25: 'Event Recovery Amount Up',
    26: 'Event Effect Up',
    27: 'Failure Rate Down',
    28: 'Energy Discount',
    29: 'Mini Game Effect Up',
    30: 'Skill Point Bonus',
    31: 'Wisdom Training Recovery Up',
    32: 'Initial Skill Points Up',
    33: 'Hint Quantity Bonus',
    41: 'All Stats Bonus',
}

# ---------------------------
# Command-line URL argument
# ---------------------------
if len(sys.argv) < 2:
    print("Usage: python3 script.py <data_url> <img_url>")
    sys.exit(1)

data_url = sys.argv[1]

# Extract page name for filename (last part of URL)
page_name = data_url.rstrip("/").split("/")[-1]

# ---------------------------
# Get HTML and buildId
# ---------------------------
html = requests.get(data_url).text
match = re.search(r'"buildId":"([^"]+)"', html)
if not match:
    print("Could not find buildId in page HTML.")
    sys.exit(1)

build_id = match.group(1)

# ---------------------------
# Fetch JSON data
# ---------------------------
json_url = f"https://gametora.com/_next/data/{build_id}/umamusume/supports/{page_name}.json"
data = requests.get(json_url).json()
item = data["pageProps"]["itemData"]

# ---------------------------
# Helper function to get final effect value
# ---------------------------
def final_value(row):
    values = row[1:]
    return max(v for v in values if v != -1)

# ---------------------------
# Generate output
# ---------------------------

lines = []

# ---------------------------
# Extract Unique Effect from HTML
# ---------------------------
import bs4  # make sure to `pip install beautifulsoup4` if not installed

soup = bs4.BeautifulSoup(html, "html.parser")
unique_div = soup.find("div", class_="supports_infobox_effect__qEhCR")
if unique_div:
    caption = unique_div.find("div", class_="supports_infobox_effect_text_caption__aeRUN")
    if caption and "Unique Effect" in caption.text:
        lines.append("Unique Effect")
        # find all inner divs under supports_infobox_effect_text__Eo_zW
        text_divs = unique_div.find("div", class_="supports_infobox_effect_text__Eo_zW")
        if text_divs:
            for d in text_divs.find_all("div", recursive=False):
                lines.append(f"    {d.text.strip()}")

# ---------------------------
# Extract Type
# ---------------------------
# Mapping from image filename to type
type_map = {
    "utx_ico_obtain_00.png": "SPEED",
    "utx_ico_obtain_01.png": "STAMINA",
    "utx_ico_obtain_02.png": "POWER",
    "utx_ico_obtain_03.png": "GUTS",
    "utx_ico_obtain_04.png": "WIT",
    "utx_ico_obtain_05.png": "PAL",
    "utx_ico_obtain_06.png": "GROUP",
}

# Find the relevant <img> inside the type box
img_tag = soup.select_one('img[src*="utx_ico_obtain_"]')

card_type = ""
if img_tag:
    src = img_tag.get("src", "")
    filename = src.split("/")[-1]
    card_type = "_" + type_map.get(filename, "")


# ---------------------------
# Extract effects
# ---------------------------

for row in item["effects"]:
    effect_id = row[0]
    value = final_value(row)
    name = effect_names.get(effect_id, f"Unknown Effect ({effect_id})")
    lines.append(f"{name}: {value}")

# Save data to file
output_file = f"outputs/{page_name}{card_type}.txt"

with open(output_file, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Data saved to {output_file}")

# Save image to file
img_url = sys.argv[2]
response = requests.get(img_url)
response.raise_for_status()  # ensures we stop if download failed

output_img = output_file.removesuffix(".txt") + ".png"
with open(output_img, "wb") as f:
    f.write(response.content)

print(f"Image saved to {output_img}")

