#!/usr/bin/python3


import re
import json
from urllib.parse import urljoin
from typing import Optional, Dict, Any, List

import requests
from bs4 import BeautifulSoup, Tag

# --- Helpers --------------------------------------------------------------

def find_tag_with_class_prefix(parent: Tag, prefix: str) -> Optional[Tag]:
    """Return the first descendant tag whose class list contains a value that startswith prefix."""
    for t in parent.find_all(True):
        classes = t.get("class") or []
        for c in classes:
            if isinstance(c, str) and c.startswith(prefix):
                return t
    return None

def find_all_tags_with_class_prefix(parent: Tag, prefix: str) -> List[Tag]:
    out = []
    for t in parent.find_all(True):
        classes = t.get("class") or []
        for c in classes:
            if isinstance(c, str) and c.startswith(prefix):
                out.append(t)
                break
    return out

def extract_details_link(tag: Tag, base_url: Optional[str] = None) -> Optional[str]:
    """
    Try many heuristics to find a Details link or URL in/around the "Details" node:
    - <a href="...">Details</a>
    - data-href / data-url / data-target attributes
    - onclick="openModal('/path')" -> extract '/path'
    - check ancestors up to a few levels
    """
    # find a node that contains the exact text 'Details' (case-insensitive)
    details_node = tag.find(string=lambda s: isinstance(s, str) and s.strip().lower() == "details")
    if details_node:
        details_el = details_node.parent
    else:
        # fallback: look for any element that looks like a clickable label
        details_el = tag.find(lambda t: t.name in ("a", "button", "div") and any("detail" in (c or "") for c in (t.get("class") or [])))

    candidates = []
    if details_el:
        candidates.append(details_el)
        candidates.extend(list(details_el.parents)[:4])  # check ancestors too

    # Also consider any <a> that contains "details" text or a likely details href
    for a in tag.find_all('a'):
        if a.get_text(strip=True).lower() == "details" or (a.get('href') and 'detail' in a.get('href')):
            candidates.append(a)

    # search candidate attributes
    for el in candidates:
        if not isinstance(el, Tag):
            continue
        # obvious href on <a>
        if el.name == "a" and el.has_attr("href"):
            href = el['href'].strip()
            if href:
                return urljoin(base_url, href) if base_url else href
        # data-* attributes
        for attr in ("data-href", "data-url", "data-target", "data-link", "data-detail", "data-id"):
            if el.has_attr(attr):
                val = el[attr].strip()
                if val:
                    return urljoin(base_url, val) if base_url else val
        # onclick pattern (extract first quoted path)
        if el.has_attr("onclick"):
            onclick = el["onclick"]
            m = re.search(r"""['"](/[^'"]+)['"]""", onclick)
            if m:
                return urljoin(base_url, m.group(1)) if base_url else m.group(1)
            # sometimes onclick contains full URL
            m2 = re.search(r"""['"](https?://[^'"]+)['"]""", onclick)
            if m2:
                return m2.group(1)

    # final fallback: look for any href under this row that appears to be a detail link
    for a in tag.find_all('a', href=True):
        href = a['href']
        if 'race' in href or 'detail' in href or 'umamusume' in href:
            return urljoin(base_url, href) if base_url else href

    return None

def parse_race_div(div: Tag, base_url: Optional[str] = None) -> Dict[str, Any]:
    """Parse the race row and return a dict of extracted fields."""
    out: Dict[str, Any] = {}

    # Banner image (if present)
    img_tag = div.find('img')
    if img_tag and img_tag.has_attr('src'):
        out['banner_src'] = urljoin(base_url, img_tag['src']) if base_url else img_tag['src']
    else:
        out['banner_src'] = None

    # Race name
    name_tag = find_tag_with_class_prefix(div, 'races_name')
    if name_tag:
        # the name itself is often inside a child with races_item__...
        name_item = name_tag.find(lambda t: t.name in ('div','span') and (t.get('class') or []) and any(c.startswith('races_item') for c in t.get('class')))
        out['name'] = name_item.get_text(strip=True) if name_item else name_tag.get_text(strip=True)
    else:
        # fallback: first large text
        out['name'] = div.get_text(" ", strip=True).splitlines()[0] if div.get_text() else None

    # Grade ribbon image (if present)
    ribbon_tag = find_tag_with_class_prefix(div, 'races_ribbon')
    ribbon_img = ribbon_tag.find('img') if ribbon_tag else None
    if ribbon_img and ribbon_img.has_attr('src'):
        out['grade_img'] = urljoin(base_url, ribbon_img['src']) if base_url else ribbon_img['src']
        out['grade_alt'] = ribbon_img.get('alt') or None
    else:
        out['grade_img'] = None
        out['grade_alt'] = None

    # Date: First Year / Second Year etc & month+half (e.g. "September 2")
    date_tag = find_tag_with_class_prefix(div, 'races_date')
    if date_tag:
        date_items = date_tag.find_all(lambda t: t.name in ('div','span') and (t.get('class') or []) and any(c.startswith('races_item') for c in t.get('class')))
        if len(date_items) >= 2:
            out['phase'] = date_items[0].get_text(strip=True)   # "First Year"
            month_half = date_items[1].get_text(strip=True)    # "September 2"
        else:
            txt = date_tag.get_text(" ", strip=True)
            parts = txt.split()
            out['phase'] = parts[0] if parts else None
            month_half = parts[1] if len(parts) > 1 else ""
    else:
        out['phase'] = None
        month_half = ""

    # normalize phase -> optional short key
    phase_map = {"First Year": "Junior", "Second Year": "Classic", "Third Year": "Senior"}
    out['phase_key'] = phase_map.get(out['phase'], out['phase'])

    # parse month + half
    m = re.match(r"([A-Za-z]+)\s*(\d)", month_half)
    if m:
        out['month_name'] = m.group(1)
        out['half'] = int(m.group(2))   # 1 = early, 2 = late (as you specified)
    else:
        out['month_name'] = None
        out['half'] = None

    # Right side: terrain, racetrack, distance label and distance meters
    desc_tag = find_tag_with_class_prefix(div, 'races_desc_right')
    out['terrain'] = None
    out['racetrack'] = None
    out['distance_label'] = None
    out['distance_m'] = None
    if desc_tag:
        # find the per-item divs (the snippet shows two items: terrain+racetrack and distance+meters)
        items = desc_tag.find_all(lambda t: t.name in ('div','span') and (t.get('class') or []) and any(c.startswith('races_item') for c in t.get('class')))
        if not items:
            # fallback: direct children
            items = [c for c in desc_tag.find_all(['div','span'], recursive=False)]
        if items:
            # first item: terrain + nested racetrack
            first_texts = [s.strip() for s in items[0].stripped_strings]
            if first_texts:
                out['terrain'] = first_texts[0]
                if len(first_texts) > 1:
                    # racetrack often appears as "⇒ Nakayama" or similar
                    racetrack_text = first_texts[1]
                    out['racetrack'] = racetrack_text.lstrip('⇒').strip()
            # second item: distance label and meters
            if len(items) > 1:
                second_texts = [s.strip() for s in items[1].stripped_strings]
                if second_texts:
                    out['distance_label'] = second_texts[0]
                    if len(second_texts) > 1:
                        m2 = re.search(r"(\d+)", second_texts[1].replace(',', ''))
                        if m2:
                            out['distance_m'] = int(m2.group(1))

    # details link (best-effort)
    out['details_url'] = extract_details_link(div, base_url=base_url)

    return out

# --- High-level usage ----------------------------------------------------

def parse_page_html(html: str, base_url: Optional[str] = None) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    rows = []
    # find all top-level race rows by looking for class prefix 'races_row'
    for row in soup.find_all(lambda t: t.name == "div" and t.get("class") and any(c.startswith("races_row") for c in t.get("class"))):
        parsed = parse_race_div(row, base_url=base_url)
        rows.append(parsed)
    return rows

def fetch_and_parse(url: str) -> List[Dict[str, Any]]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; parser/1.0)"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return parse_page_html(r.text, base_url=url)

# --- Example: parse your pasted snippet ----------------------------------
if __name__ == "__main__":
    sample_html = r'''<div class="races_row__yg6YI races_stripes__z3_xN"><div class="races_image__Z_Ufn"><div class="races_image_wrapper__j9fBN"><span style="max-width: 128px; max-height: 64px; display: inline-block; margin: auto; filter: var(--image-dim);"><img src="/images/umamusume/en/race_banners/thum_race_rt_000_4502_00.png" loading="lazy" alt="" style="max-width: 100%; height: auto;"></span></div></div><div class="races_name__sPwXg"><div class="races_item__UAtcS">Saffron Sho</div></div><div class="races_ribbon__N13Bi"><div class="races_item__UAtcS"><span style="max-width: 68px; max-height: 26px; display: inline-block; filter: var(--image-dim);"><img src="/images/umamusume/race_ribbons/utx_txt_grade_ribbon_06.png" loading="lazy" alt="" layout="intrinsic" style="max-width: 100%; height: auto;"></span></div><div class="utils_linkcolor__rvv3k">Details</div></div><div class="races_date__dMOy_"><div class="races_item__UAtcS">First Year</div><div class="races_item__UAtcS">September 2</div></div><div class="races_desc_right__wV_1d"><div class="races_item__UAtcS">Turf<div class="races_tabtext__SoLhs"><span>⇒</span> Nakayama</div></div><div class="races_item__UAtcS">Mile<div class="races_tabtext__SoLhs">1600 m</div></div></div></div>'''

    parsed_rows = parse_page_html(sample_html, base_url="https://gametora.com")
    print(json.dumps(parsed_rows, ensure_ascii=False, indent=2))

