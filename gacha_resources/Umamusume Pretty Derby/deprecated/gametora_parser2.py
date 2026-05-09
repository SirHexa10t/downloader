#!/usr/bin/python3

from bs4 import BeautifulSoup
import json

# Load the HTML you saved
with open("tametora_page.txt", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

races = []

for row in soup.select("div.races_row__yg6YI"):
    race = {}

    # Race name
    name_tag = row.select_one(".races_name__sPwXg .races_item__UAtcS")
    race["name"] = name_tag.get_text(strip=True) if name_tag else None

    # Year + Date (e.g., "First Year", "September 2")
    date_tags = row.select(".races_date__dMOy_ .races_item__UAtcS")
    if len(date_tags) >= 2:
        race["year"] = date_tags[0].get_text(strip=True)
        race["date"] = date_tags[1].get_text(strip=True)
    else:
        race["year"] = race["date"] = None

    # Terrain + Racetrack
    desc_tags = row.select(".races_desc_right__wV_1d .races_item__UAtcS")
    if len(desc_tags) >= 1:
        terrain = desc_tags[0].get_text(strip=True).split("\n")[0]
        race["terrain"] = terrain
        racetrack_tag = desc_tags[0].select_one(".races_tabtext__SoLhs")
        race["racetrack"] = racetrack_tag.get_text(strip=True).lstrip("⇒ ") if racetrack_tag else None
    if len(desc_tags) >= 2:
        race["distance_type"] = desc_tags[1].get_text(strip=True).split("\n")[0]
        dist_tag = desc_tags[1].select_one(".races_tabtext__SoLhs")
        if dist_tag:
            dist_txt = dist_tag.get_text(strip=True).replace("m", "").strip()
            race["distance_m"] = int(dist_txt) if dist_txt.isdigit() else dist_txt
        else:
             race["distance_m"] = None

    # Grade ribbon image (if present)
    ribbon_img = row.select_one(".races_ribbon__N13Bi img")
    race["grade_img"] = ribbon_img["src"] if ribbon_img else None

    # Details link
    details_btn = row.find("div", string="Details")
    if details_btn and details_btn.parent.has_attr("href"):
        race["details_url"] = details_btn.parent["href"]
    else:
        race["details_url"] = None

    races.append(race)

# Pretty-print a sample of the extracted races
print(json.dumps(races[:5], indent=2, ensure_ascii=False))

# Save all to JSON
with open("parsed_races.json", "w", encoding="utf-8") as f:
    json.dump(races, f, indent=2, ensure_ascii=False)

