"""Tests for the collage engine (filtered_results/build_collages.py)."""

from pathlib import Path

from PIL import Image

import build_collages as bc

RACE_PATTERN = "Increases stat gain from races"

SAMPLE_TXT = """Unique Effect
    Increases the effectiveness of training performed together (5%)
    Increases stat gain from races (5%)
Friendship Bonus: 20
Race Bonus: 10
Energy Discount: -5
"""


# ---------------------------
# Parsing scraped txt files
# ---------------------------

class TestParseCardTxt:
    def test_splits_stats_and_unique_lines(self, tmp_path):
        f = tmp_path / "card.txt"
        f.write_text(SAMPLE_TXT)
        stats, unique = bc.parse_card_txt(f)
        assert stats == {"Friendship Bonus": 20, "Race Bonus": 10,
                         "Energy Discount": -5}
        assert unique == [
            "Increases the effectiveness of training performed together (5%)",
            "Increases stat gain from races (5%)",
        ]

    def test_card_without_unique_block(self, tmp_path):
        f = tmp_path / "card.txt"
        f.write_text("Race Bonus: 5\nMood Bonus: 30")
        stats, unique = bc.parse_card_txt(f)
        assert stats == {"Race Bonus": 5, "Mood Bonus": 30}
        assert unique == []

    def test_non_numeric_lines_ignored(self, tmp_path):
        f = tmp_path / "card.txt"
        f.write_text("Race Bonus: 5\nSome prose without value\nBad: 3x")
        stats, _ = bc.parse_card_txt(f)
        assert stats == {"Race Bonus": 5}


class TestUniqueValue:
    LINES = ["Increases stat gain from races (5%)",
             "Increases the effectiveness of Friendship Training (10%)"]

    def test_matching_pattern_returns_percentage(self):
        assert bc.unique_value(self.LINES, [RACE_PATTERN]) == (5, [])
        assert bc.unique_value(
            self.LINES,
            ["Increases the effectiveness of Friendship Training"]) == (10, [])

    def test_no_match_or_no_patterns_is_zero(self):
        assert bc.unique_value(self.LINES, ["Nonexistent bonus"]) == (0, [])
        assert bc.unique_value(self.LINES, []) == (0, [])
        assert bc.unique_value([], [RACE_PATTERN]) == (0, [])

    def test_matching_lines_sum_up(self):
        value, _ = bc.unique_value(
            self.LINES, [RACE_PATTERN,
                         "Increases the effectiveness of Friendship Training"])
        assert value == 15


class TestConditionalPatterns:
    FULL_BOND = "Gain Friendship Bonus (20) when the bond gauge is full"

    def test_number_without_percent_sign_counts(self):
        assert bc.unique_value([self.FULL_BOND], [], ["Gain Friendship Bonus"]) \
            == (20, [self.FULL_BOND])

    def test_line_max_prefers_stacking_total_over_per_step(self):
        line = ("Gain Friendship Bonus (3) every time you do friendship training "
                "with this card, up to 5 times for a total of (15)")
        value, conditions = bc.unique_value(
            [line], [], ["Gain Friendship Bonus", "up to 5 times for a total of"])
        assert value == 15
        assert conditions == [line]

    def test_captures_number_adjacent_to_pattern_not_later_ones(self):
        line = ("Gain Friendship Bonus (10) and Mood Effect (15) "
                "when the bond gauge is at least 80")
        assert bc.unique_value([line], [], ["Gain Friendship Bonus"]) \
            == (10, [line])

    def test_pattern_with_own_capture_group_used_verbatim(self):
        line = ("The higher the combined facility level, the higher "
                "Training Effectiveness you'll gain (up to 20)")
        value, conditions = bc.unique_value(
            [line], [], [r"you'll gain \(up to (\d+)\)"])
        assert value == 20
        assert conditions == [line]

    def test_unconditional_and_conditional_lines_sum(self):
        lines = ["Increases the effectiveness of Friendship Training (10%)",
                 self.FULL_BOND]
        value, conditions = bc.unique_value(
            lines, ["Increases the effectiveness of Friendship Training"],
            ["Gain Friendship Bonus"])
        assert value == 30
        assert conditions == [self.FULL_BOND]  # only the conditional line listed


class TestFormatRow:
    def test_condition_appended_after_the_data(self):
        row = bc.format_row({
            "stem": "30101-agnes-tachyon_SPEED", "total": 40,
            "unique": 20, "stat": 20,
            "conditions": ["Gain Friendship Bonus (20) when the bond gauge is full"],
        })
        assert row.endswith(
            "(unique=20, mlb_stat=20)  "
            "[unique-condition: Gain Friendship Bonus (20) when the bond gauge is full]")

    def test_unconditional_row_has_no_trailer(self):
        row = bc.format_row({"stem": "30005-vodka_POWER", "total": 45,
                             "unique": 10, "stat": 35, "conditions": []})
        assert row.endswith("(unique=10, mlb_stat=35)")


# ---------------------------
# Collecting and ranking cards
# ---------------------------

def write_card(outputs, stem, race=0, unique_race=0, with_png=True):
    lines = []
    if unique_race:
        lines += ["Unique Effect",
                  f"    Increases stat gain from races ({unique_race}%)"]
    lines.append(f"Race Bonus: {race}")
    (outputs / f"{stem}.txt").write_text("\n".join(lines))
    if with_png:
        Image.new("RGBA", (16, 16), (200, 0, 0, 255)).save(outputs / f"{stem}.png")


class TestCollectCards:
    def test_totals_and_ordering(self, tmp_path):
        write_card(tmp_path, "30001-a_SPEED", race=10, unique_race=5)
        write_card(tmp_path, "30002-b_WIT", race=15)
        write_card(tmp_path, "30003-c_GUTS", race=5)
        write_card(tmp_path, "30004-d_PAL", race=0)  # excluded: no bonus at all
        cards = bc.collect_cards(tmp_path, "Race Bonus", [RACE_PATTERN])
        assert [(c["stem"], c["total"], c["stat"], c["unique"]) for c in cards] == [
            ("30001-a_SPEED", 15, 10, 5),
            ("30002-b_WIT", 15, 15, 0),
            ("30003-c_GUTS", 5, 5, 0),
        ]

    def test_unique_only_card_is_included(self, tmp_path):
        (tmp_path / "30005-e_WIT.txt").write_text(
            "Unique Effect\n    Increases stat gain from races (5%)\nMood Bonus: 30")
        cards = bc.collect_cards(tmp_path, "Race Bonus", [RACE_PATTERN])
        assert [(c["stem"], c["total"]) for c in cards] == [("30005-e_WIT", 5)]


# ---------------------------
# Grid building
# ---------------------------

def make_icons(icon_dir):
    icon_dir.mkdir()
    for name, color in [("SPEED", (0, 0, 255, 255)), ("WIT", (0, 255, 0, 255))]:
        Image.new("RGBA", (8, 8), color).save(icon_dir / f"{name}.png")


def make_cards(tmp_path, stem_colors):
    pngs = []
    for stem, color in stem_colors.items():
        png = tmp_path / f"{stem}.png"
        Image.new("RGBA", (30, 30), color).save(png)
        pngs.append(png)
    return pngs


class TestBuildGrid:
    def test_game_type_order_and_icons(self, tmp_path):
        icons = tmp_path / "icons"
        make_icons(icons)
        colors = {"20001-a_WIT": (10, 10, 10, 255),
                  "20002-b_SPEED": (20, 20, 20, 255),
                  "20003-c_GUTS": (30, 30, 30, 255)}
        out = tmp_path / "grid.png"
        bc.build_grid(make_cards(tmp_path, colors), icons, out)

        grid = Image.open(out)
        assert grid.size == (60, 60)  # 3 cards -> 2x2 tiles of 30px
        # game type order: SPEED before GUTS before WIT, regardless of id
        assert grid.getpixel((0, 0)) == colors["20002-b_SPEED"]
        assert grid.getpixel((30, 0)) == colors["20003-c_GUTS"]
        assert grid.getpixel((0, 30)) == colors["20001-a_WIT"]
        # type icon (tile//3 = 10px) pasted into each tile's top-right corner
        assert grid.getpixel((29, 0)) == (0, 0, 255, 255)   # SPEED icon
        assert grid.getpixel((59, 0)) == colors["20003-c_GUTS"]  # no GUTS icon file
        assert grid.getpixel((29, 30)) == (0, 255, 0, 255)  # WIT icon

    def test_rarity_order_within_type(self, tmp_path):
        colors = {"10005-r-card_SPEED": (1, 1, 1, 255),
                  "20003-sr-card_SPEED": (2, 2, 2, 255),
                  "30001-ssr-card_SPEED": (3, 3, 3, 255)}
        out = tmp_path / "grid.png"
        bc.build_grid(make_cards(tmp_path, colors), tmp_path / "no_icons", out)

        grid = Image.open(out)
        assert grid.getpixel((0, 0)) == colors["30001-ssr-card_SPEED"]  # SSR first
        assert grid.getpixel((30, 0)) == colors["20003-sr-card_SPEED"]
        assert grid.getpixel((0, 30)) == colors["10005-r-card_SPEED"]

    def test_unknown_type_sorts_last(self, tmp_path):
        colors = {"30500-mystery": (9, 9, 9, 255),
                  "10001-plain_GROUP": (4, 4, 4, 255)}
        out = tmp_path / "grid.png"
        bc.build_grid(make_cards(tmp_path, colors), tmp_path / "no_icons", out)

        grid = Image.open(out)
        assert grid.getpixel((0, 0)) == colors["10001-plain_GROUP"]
        assert grid.getpixel((30, 0)) == colors["30500-mystery"]

    def test_no_icons_dir_builds_plain_grid(self, tmp_path):
        png = tmp_path / "20001-a_WIT.png"
        Image.new("RGBA", (30, 30), (1, 2, 3, 255)).save(png)
        out = tmp_path / "grid.png"
        bc.build_grid([png], tmp_path / "missing_icons", out)
        assert Image.open(out).size == (30, 30)


class TestBuildBucket:
    def collect(self, outputs):
        return bc.collect_cards(outputs, "Race Bonus", [RACE_PATTERN])

    def test_grid_and_fresh_folder(self, tmp_path, monkeypatch):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        write_card(outputs, "30001-a_SPEED", race=15)
        monkeypatch.chdir(tmp_path)

        stale_dir = tmp_path / "race_bonus_15"
        stale_dir.mkdir()
        (stale_dir / "stale-card.png").write_bytes(b"junk")

        bc.build_bucket(self.collect(outputs), 15, "race_bonus",
                        tmp_path / "no_icons", make_folder=True)

        assert (tmp_path / "race_bonus_15_grid.png").exists()
        members = [p.name for p in stale_dir.iterdir()]
        assert members == ["30001-a_SPEED.png"]  # stale file cleaned out

    def test_card_without_png_is_skipped_with_warning(self, tmp_path, monkeypatch, capsys):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        write_card(outputs, "30001-a_SPEED", race=15)
        write_card(outputs, "30002-b_WIT", race=15, with_png=False)
        monkeypatch.chdir(tmp_path)

        bc.build_bucket(self.collect(outputs), 15, "race_bonus",
                        tmp_path / "no_icons", make_folder=False)

        out = capsys.readouterr().out
        assert "30002-b_WIT has no .png" in out
        assert Image.open(tmp_path / "race_bonus_15_grid.png").size == (16, 16)

    def test_empty_bucket_builds_nothing(self, tmp_path, monkeypatch, capsys):
        outputs = tmp_path / "outputs"
        outputs.mkdir()
        monkeypatch.chdir(tmp_path)
        bc.build_bucket([], 15, "race_bonus", tmp_path / "no_icons", make_folder=True)
        assert "no cards with total 15" in capsys.readouterr().out
        assert not (tmp_path / "race_bonus_15_grid.png").exists()
        assert not (tmp_path / "race_bonus_15").exists()
