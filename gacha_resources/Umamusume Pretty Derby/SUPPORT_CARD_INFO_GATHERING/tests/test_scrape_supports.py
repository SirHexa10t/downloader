"""Tests for the unified scraper (scrape_supports.py).

Network-free: card pages, data json and images are stubbed. The saved
listing html / stat table / links file in the repo root are used as real
fixtures when present, and those tests skip if the files have been renamed.
"""

import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import scrape_supports as ss

ROOT = Path(__file__).resolve().parent.parent


def latest(pattern):
    files = sorted(ROOT.glob(pattern))
    if not files:
        pytest.skip(f"no {pattern} in repo root")
    return files[-1]


# ---------------------------
# Effect name lookup
# ---------------------------

class TestBuildEffectNames:
    def test_prefers_eon_name_over_plain_english(self, tmp_path):
        table = tmp_path / "t.json"
        table.write_text(json.dumps([
            {"id": 1, "name_en": "Plain", "name_en_eon": "EoN"},
            {"id": 2, "name_en": "Only Plain"},
            {"id": 3, "name_ja": "英語なし"},
        ]))
        assert ss.build_effect_names(table) == {1: "EoN", 2: "Only Plain"}

    def test_real_stat_table_covers_known_effects(self):
        names = ss.build_effect_names(latest("stat_table_*.json"))
        assert names[1] == "Friendship Bonus"
        assert names[15] == "Race Bonus"
        assert names[41] == "All Stats Bonus"
        assert names[9991] == "Increases Stats from Hints"


# ---------------------------
# Listing page -> links
# ---------------------------

class TestExtractSupportLinks:
    def test_real_listing_page(self):
        links = ss.extract_support_links(latest("gametora_supports_*.html"))
        assert len(links) > 500
        for page_url, img_url in links:
            assert page_url.startswith("https://gametora.com/umamusume/supports/")
            assert img_url.startswith(
                "https://gametora.com/images/umamusume/supports/support_card_s_")
        assert links == sorted(links)
        assert len({p for p, _ in links}) == len(links)

    def test_matches_previously_generated_links_file(self):
        links = ss.extract_support_links(latest("gametora_supports_*.html"))
        lines = latest("support_links_*.txt").read_text().splitlines()
        expected = [tuple(line.split()) for line in lines if line.strip()]
        assert links == expected


# ---------------------------
# Card page parsing
# ---------------------------

CARD_HTML = """
<html><body>
<script>self.__next_f={"buildId":"testbuild123"}</script>
<img src="/images/umamusume/utx_ico_obtain_04.png">
<div class="supports_infobox_effect__NEWHASH">
  <div class="supports_infobox_effect_text_caption__NEWHASH">Unique Effect</div>
  <div class="supports_infobox_effect_text__NEWHASH">
    <div>Increases stat gain from races (5%)</div>
    <div>Increases the effectiveness of Friendship Training (10%)</div>
  </div>
</div>
</body></html>
"""


class TestCardPageParsing:
    def test_final_value_takes_max_ignoring_locked_levels(self):
        assert ss.final_value([15, 1, 2, 3]) == 3
        assert ss.final_value([15, 10, -1, -1]) == 10
        assert ss.final_value([15, -1, 5, -1, 20]) == 20

    def test_unique_effect_survives_css_module_hash_change(self):
        soup = BeautifulSoup(CARD_HTML, "html.parser")
        assert ss.parse_unique_effect(soup) == [
            "Unique Effect",
            "    Increases stat gain from races (5%)",
            "    Increases the effectiveness of Friendship Training (10%)",
        ]

    def test_card_without_unique_effect(self):
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        assert ss.parse_unique_effect(soup) == []

    def test_card_type_from_icon(self):
        soup = BeautifulSoup(CARD_HTML, "html.parser")
        assert ss.parse_card_type(soup) == "_WIT"

    def test_card_type_unknown_icon_and_missing_icon(self):
        soup = BeautifulSoup('<img src="/x/utx_ico_obtain_99.png">', "html.parser")
        assert ss.parse_card_type(soup) == "_"
        assert ss.parse_card_type(BeautifulSoup("", "html.parser")) == ""


# ---------------------------
# Resume logic
# ---------------------------

class TestIsDone:
    def make(self, outdir, *names):
        for name in names:
            (outdir / name).write_text("x")

    def test_done_when_txt_and_png_exist(self, tmp_path):
        self.make(tmp_path, "10001-special-week_GUTS.txt", "10001-special-week_GUTS.png")
        assert ss.is_done(tmp_path, "10001-special-week")

    def test_every_suffix_variant_counts(self, tmp_path):
        for suffix in ["_SPEED", "_PAL", "_GROUP", "_", ""]:
            slug = f"2000{len(suffix)}-someone"
            self.make(tmp_path, f"{slug}{suffix}.txt", f"{slug}{suffix}.png")
            assert ss.is_done(tmp_path, slug), suffix

    def test_not_done_when_either_file_missing(self, tmp_path):
        self.make(tmp_path, "10002-a_SPEED.txt")
        self.make(tmp_path, "10003-b_SPEED.png")
        assert not ss.is_done(tmp_path, "10002-a")
        assert not ss.is_done(tmp_path, "10003-b")

    def test_other_cards_files_do_not_match(self, tmp_path):
        self.make(tmp_path, "10001-special-week_GUTS.txt", "10001-special-week_GUTS.png")
        assert not ss.is_done(tmp_path, "10001-special")


class TestWriteAtomic:
    def test_writes_text_and_bytes_without_leftovers(self, tmp_path):
        ss.write_atomic(tmp_path / "a.txt", "hello")
        ss.write_atomic(tmp_path / "a.png", b"\x89PNG")
        assert (tmp_path / "a.txt").read_text() == "hello"
        assert (tmp_path / "a.png").read_bytes() == b"\x89PNG"
        assert list(tmp_path.glob("*.tmp")) == []


# ---------------------------
# Whole-card scrape (stubbed network)
# ---------------------------

class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    @property
    def text(self):
        return self.payload

    @property
    def content(self):
        return self.payload

    def json(self):
        return self.payload


class TestScrapeCard:
    def fake_fetch(self, session, url):
        if url.endswith(".json"):
            assert "testbuild123" in url
            return FakeResponse({"pageProps": {"itemData": {
                "effects": [[1, 20, 25, -1], [15, -1, 5, 10]],
            }}})
        if url.endswith(".png"):
            return FakeResponse(b"png-bytes")
        return FakeResponse(CARD_HTML)

    def test_writes_expected_txt_and_png(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ss, "fetch", self.fake_fetch)
        had_unique = ss.scrape_card(
            None, "https://gametora.com/umamusume/supports/30010-fine-motion",
            "https://gametora.com/images/x/support_card_s_30010.png",
            {1: "Friendship Bonus", 15: "Race Bonus"}, tmp_path)

        assert had_unique
        txt = tmp_path / "30010-fine-motion_WIT.txt"
        assert txt.read_text() == (
            "Unique Effect\n"
            "    Increases stat gain from races (5%)\n"
            "    Increases the effectiveness of Friendship Training (10%)\n"
            "Friendship Bonus: 25\n"
            "Race Bonus: 10"
        )
        assert (tmp_path / "30010-fine-motion_WIT.png").read_bytes() == b"png-bytes"

    def test_unknown_effect_id_is_labelled(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ss, "fetch", self.fake_fetch)
        ss.scrape_card(None, "https://x/supports/30010-fine-motion",
                       "https://x/support_card_s_30010.png", {}, tmp_path)
        content = (tmp_path / "30010-fine-motion_WIT.txt").read_text()
        assert "Unknown Effect (1): 25" in content
        assert "Unknown Effect (15): 10" in content

    def test_missing_build_id_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ss, "fetch",
                            lambda s, u: FakeResponse("<html>no build id</html>"))
        with pytest.raises(RuntimeError, match="buildId"):
            ss.scrape_card(None, "https://x/supports/30010-fine-motion",
                           "https://x/i.png", {}, tmp_path)
