"""Tests for bullet and cartridge display_name computation."""

import pytest

from drift.display_name import compute_bullet_display_name, compute_cartridge_display_name

# ---------------------------------------------------------------------------
# Bullet display_name tests
# ---------------------------------------------------------------------------


class TestBulletDisplayName:
    """Test compute_bullet_display_name against real catalog data."""

    # -- Hornady pattern: "caliber diameter weight product_line®" --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ("30 Cal .308 150 gr CX\u00ae", "Hornady", "CX"),
            ("30 Cal .308 165 gr SST\u00ae", "Hornady", "SST"),
            ("30 Cal .308 168 gr BTHP Match\u2122", "Hornady", "BTHP Match"),
            (
                "30 Cal .308 155 gr BTHP Match\u2122 with cannelure",
                "Hornady",
                "BTHP Match with cannelure",
            ),
            ("30 Cal .308 220 gr InterLock\u00ae RN", "Hornady", "InterLock RN"),
            ("30 Cal 308 125 gr ECX\u2122", "Hornady", "ECX"),
            # en-dash (U+2011) in source → regular hyphen in output
            ("6.5mm .264 100 gr ELD\u2011VT\u00ae", "Hornady", "ELD-VT"),
            ("6.5mm .264 143 gr ELD\u2011X\u00ae", "Hornady", "ELD-X"),
            ("6.5mm .264 147 gr ELD\u00ae Match", "Hornady", "ELD Match"),
            ("6.5mm .264 129 gr InterLock\u00ae SP", "Hornady", "InterLock SP"),
            ("6.5mm .264 140 gr BTHP Match\u2122", "Hornady", "BTHP Match"),
            ("30 cal .308 195 gr ELD\u00ae Match", "Hornady", "ELD Match"),
            ("338 Cal .338 285 gr ELD\u00ae Match", "Hornady", "ELD Match"),
            ("6mm .243 108 gr ELD\u00ae Match", "Hornady", "ELD Match"),
            ("7mm .284 175 gr ELD\u2011X\u00ae", "Hornady", "ELD-X"),
            ("30 Cal .308 174 gr ELD\u2011VT\u00ae", "Hornady", "ELD-VT"),
            ("6mm .243 90 gr CX\u00ae", "Hornady", "CX"),
            ("338 cal .338 270 gr ELD-X\u00ae", "Hornady", "ELD-X"),
        ],
    )
    def test_hornady(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Sierra pattern: "CALIBER WEIGHT DESCRIPTION" --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ("30 CAL 175 GR HPBT MATCHKING (SMK)", "Sierra Bullets", "HPBT MatchKing"),
            ("30 CAL 150 GR HPBT MATCHKING (SMK)", "Sierra Bullets", "HPBT MatchKing"),
            ("30 CAL 190 GR HPBT MATCHKING (SMK)", "Sierra Bullets", "HPBT MatchKing"),
            ("6.5MM 140 GR HPBT MatchKing (SMK)", "Sierra Bullets", "HPBT MatchKing"),
            ("6MM 107 GR HPBT/CN MatchKing (SMK)", "Sierra Bullets", "HPBT/CN MatchKing"),
            ("6MM 105 GR HPBT/CN MatchKing (SMK)", "Sierra Bullets", "HPBT/CN MatchKing"),
            ("338 CAL 250 GR HPBT MATCHKING (SMK)", "Sierra Bullets", "HPBT MatchKing"),
            ("338 CAL 300 GR HPBT MATCHKING (SMK)", "Sierra Bullets", "HPBT MatchKing"),
        ],
    )
    def test_sierra(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Berger pattern --

    def test_berger(self):
        result = compute_bullet_display_name(
            "6.5 mm 130 Grain AR Hybrid OTM Tactical Rifle Bullet",
            manufacturer_name="Berger Bullets",
        )
        assert result == "AR Hybrid OTM Tactical"

    # -- Federal pattern: "description, .diameter, weight" --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ("Fusion Component Bullet, .264, 140 Grain", "Federal", "Fusion"),
            ("Terminal Ascent Component Bullet, .308, 175 Grain", "Federal", "Terminal Ascent"),
            ("Terminal Ascent Component Bullet, .264, 130 Grain", "Federal", "Terminal Ascent"),
            ("Trophy Bonded Tip Component Bullet, .308, 165 Grain", "Federal", "Trophy Bonded Tip"),
            ("Terminal Ascent 7mm .284 170 gr", "Federal", "Terminal Ascent"),
            ("Varmint Hollow Point Bullet, .308, 130 Grain", "Speer", "Varmint Hollow Point"),
        ],
    )
    def test_federal_speer(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Lapua pattern: "metric / imperial description SKU" --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ("9,7 g / 150 gr Mega SP E469", "Lapua", "Mega SP"),
            ("12,0 g / 185 gr Scenar OTM GB432", "Lapua", "Scenar OTM"),
            ("7,8 g / 120 gr Scenar-L OTM GB547", "Lapua", "Scenar-L OTM"),
        ],
    )
    def test_lapua(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Barnes pattern: 'diameter" caliber product weight description' --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ('0.308" 30-30 WIN TSX 150 GR FN FB', "Barnes Bullets", "TSX FN FB"),
            ('0.284" 7MM TSX FB 160 GR', "Barnes Bullets", "TSX FB"),
        ],
    )
    def test_barnes(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Nosler pattern: "caliber weight description (count)" --

    @pytest.mark.parametrize(
        "name, manufacturer, expected",
        [
            ("30 Caliber 168gr HPBT Custom Competition (100ct)", "Nosler", "HPBT Custom Competition"),
            ("30 Caliber 180gr PPT Partition (50ct)", "Nosler", "PPT Partition"),
        ],
    )
    def test_nosler(self, name, manufacturer, expected):
        result = compute_bullet_display_name(name, manufacturer_name=manufacturer)
        assert result == expected

    # -- Swift pattern --

    def test_swift(self):
        result = compute_bullet_display_name(
            "Scirocco Rifle Bullets Cal. 7MM | 150 gr",
            manufacturer_name="Swift Bullet Company",
        )
        assert result == "Scirocco"

    # -- Cutting Edge pattern --

    def test_cutting_edge(self):
        result = compute_bullet_display_name(
            ".308 SINGLE FEED Lazer-Tipped Hollow Point - 50ct",
            manufacturer_name="Cutting Edge Bullets",
        )
        assert result == "SINGLE FEED Lazer-Tipped Hollow Point"

    # -- Edge cases --

    def test_idempotency(self):
        """Running the cleaner twice produces the same output."""
        name = "30 Cal .308 168 gr BTHP Match\u2122"
        first = compute_bullet_display_name(name, manufacturer_name="Hornady")
        second = compute_bullet_display_name(first, manufacturer_name="Hornady")
        assert first == second

    def test_product_line_fallback(self):
        """Falls back to product_line when name cleaning produces empty result."""
        result = compute_bullet_display_name("", product_line="ELD-X", manufacturer_name="Hornady")
        assert result == "ELD-X"


# ---------------------------------------------------------------------------
# Cartridge display_name tests
# ---------------------------------------------------------------------------


class TestCartridgeDisplayName:
    """Test compute_cartridge_display_name against real catalog data."""

    # -- Hornady pattern: "caliber weight bullet product_line" --

    @pytest.mark.parametrize(
        "name, manufacturer, product_line, bullet_pl, expected",
        [
            (
                "6.5 Creedmoor 143 gr ELD-X Precision Hunter",
                "Hornady",
                "Precision Hunter",
                "ELD-X",
                "Precision Hunter ELD-X",
            ),
            (
                "6.5 Creedmoor 147 gr ELD\u00ae Match",
                "Hornady",
                "Match\u2122",
                "ELD Match",
                "ELD Match",
            ),
            (
                "6.5 Creedmoor 95 gr V-MAX Varmint Express",
                "Hornady",
                "Varmint Express\u00ae",
                "V-MAX",
                "Varmint Express V-MAX",
            ),
            (
                "6.5 Creedmoor 100 gr ELD\u2011VT\u2122 V\u2011Match\u2122",
                "Hornady",
                "V-MATCH\u00ae",
                "ELD-VT",
                "V-Match ELD-VT",
            ),
            (
                "6.5 Creedmoor 129 gr SST\u00ae American Whitetail\u00ae TIPPED",
                "Hornady",
                "American Whitetail\u00ae TIPPED",
                "SST",
                "American Whitetail SST",
            ),
            (
                "6.5 Creedmoor 140 gr BTHP American Gunner\u00ae",
                "Hornady",
                "American Gunner\u00ae",
                "BTHP Match",
                "American Gunner BTHP Match",
            ),
            (
                "308 Win 150 gr CX\u2122 Outfitter\u00ae",
                "Hornady",
                "Outfitter\u00ae",
                "CX",
                "Outfitter CX",
            ),
            (
                "308 Win 168 gr ELD\u00ae Match",
                "Hornady",
                "Match\u2122",
                "ELD Match",
                "ELD Match",
            ),
            (
                "308 Win 180 gr SST\u00ae Superformance\u00ae",
                "Hornady",
                "Superformance\u00ae",
                "SST",
                "Superformance SST",
            ),
            (
                "300 Win Mag 195 gr ELD\u00ae Match",
                "Hornady",
                "Match\u2122",
                "ELD Match",
                "ELD Match",
            ),
            (
                "300 Win Mag 178 gr ELD-X Precision Hunter",
                "Hornady",
                "Precision Hunter",
                "ELD-X",
                "Precision Hunter ELD-X",
            ),
            (
                "338 Lapua 285 gr ELD\u00ae Match",
                "Hornady",
                "Match\u2122",
                "ELD Match",
                "ELD Match",
            ),
            (
                "308 Win 155 gr Critical Defense\u00ae",
                "Hornady",
                "Critical Defense\u00ae",
                None,
                "Critical Defense",
            ),
            (
                "308 Win 220 gr RN Custom International\u2122",
                "Hornady",
                "Custom International\u2122",
                None,
                "Custom International",
            ),
            (
                "6.5 Creedmoor 140 gr SP Custom International\u2122",
                "Hornady",
                "Custom International\u2122",
                None,
                "Custom International",
            ),
            (
                "300 PRC 212 gr ELD-X Precision Hunter",
                "Hornady",
                "Precision Hunter",
                "ELD-X",
                "Precision Hunter ELD-X",
            ),
        ],
    )
    def test_hornady(self, name, manufacturer, product_line, bullet_pl, expected):
        result = compute_cartridge_display_name(
            name,
            product_line=product_line,
            bullet_product_line=bullet_pl,
            manufacturer_name=manufacturer,
        )
        assert result == expected

    # -- Federal pattern: "product_line, caliber, weight, bullet_desc, mv" --

    @pytest.mark.parametrize(
        "name, manufacturer, product_line, bullet_pl, expected",
        [
            (
                "Gold Medal Sierra MatchKing, 6.5 Creedmoor, 140 Grain, "
                "Sierra Matchking Boat-Tail Hollow Point, 2675 fps",
                "Federal",
                "Gold Medal",
                "MatchKing",
                "Gold Medal MatchKing",
            ),
            (
                "Terminal Ascent, 6.5 Creedmoor, 130 Grain, Terminal Ascent, 2800 fps",
                "Federal",
                "Terminal Ascent",
                "Terminal Ascent",
                "Terminal Ascent",
            ),
            (
                "Terminal Ascent, 308 Win, 175 Grain, Terminal Ascent, 2600 fps",
                "Federal",
                "Terminal Ascent",
                "Terminal Ascent",
                "Terminal Ascent",
            ),
            (
                "ELD-X, 6.5 Creedmoor, 143 Grain, ELD-X, 2700 fps",
                "Federal",
                "ELD-X",
                "ELD-X",
                "ELD-X",
            ),
            (
                "ELD-X, 308 Win, 178 Grain, ELD-X, 2610 fps",
                "Federal",
                "ELD-X",
                "ELD-X",
                "ELD-X",
            ),
            (
                "Fusion Rifle, 308 Win, 150 Grain, Fusion Soft Point, 2820 fps",
                "Federal",
                "Fusion",
                None,
                "Fusion",
            ),
            (
                "Fusion Tipped Rifle, 6.5 Creedmoor, 140 Grain, Fusion Tipped, 2715 fps",
                "Federal",
                "Fusion Tipped Rifle",
                None,
                "Fusion Tipped",
            ),
            (
                "Barnes TSX, 308 Win, 150 Grain, Barnes Triple-Shock X Bullet (TSX), 2820 fps",
                "Federal",
                "Barnes TSX",
                "TSX",
                "Barnes TSX",
            ),
            (
                "Barnes TSX, 7mm Rem Mag, 160 Grain, Barnes Triple-Shock X Bullet (TSX), 2940 fps",
                "Federal",
                "Barnes TSX",
                "TSX",
                "Barnes TSX",
            ),
            (
                "Trophy Bonded Tip, 308 Win, 165 Grain, Trophy Bonded Tip, 2700 fps",
                "Federal",
                "Trophy Bonded Tip",
                "Trophy Bonded Tip",
                "Trophy Bonded Tip",
            ),
            (
                "Gold Medal Sierra MatchKing, 7.62x51mm NATO, 175 Grain, "
                "Sierra Matchking Boat-Tail Hollow Point, 2600 fps",
                "Federal",
                "Gold Medal",
                "MatchKing",
                "Gold Medal MatchKing",
            ),
        ],
    )
    def test_federal(self, name, manufacturer, product_line, bullet_pl, expected):
        result = compute_cartridge_display_name(
            name,
            product_line=product_line,
            bullet_product_line=bullet_pl,
            manufacturer_name=manufacturer,
        )
        assert result == expected

    # -- Edge cases --

    def test_deduplication(self):
        """Terminal Ascent + Terminal Ascent → Terminal Ascent (not doubled)."""
        result = compute_cartridge_display_name(
            "Terminal Ascent, 308 Win, 175 Grain, Terminal Ascent, 2600 fps",
            product_line="Terminal Ascent",
            bullet_product_line="Terminal Ascent",
            manufacturer_name="Federal",
        )
        assert result == "Terminal Ascent"

    def test_no_product_lines_hornady_style(self):
        """When no product lines provided, derive from name."""
        result = compute_cartridge_display_name(
            "308 Win 168 gr ELD Match",
            manufacturer_name="Hornady",
        )
        assert result == "ELD Match"


class TestGracefulDegradation:
    """Verify the cleaner produces reasonable output for unknown formats."""

    def test_unknown_bullet_format_returns_something(self):
        """A totally unfamiliar format should still return a non-empty string."""
        result = compute_bullet_display_name(
            "SuperPrecision Ultra 150gr Match Grade",
            manufacturer_name="NewBrand",
        )
        assert result
        assert len(result) >= 2

    def test_unknown_bullet_falls_back_to_product_line(self):
        """If cleaning produces nothing, product_line is the fallback."""
        result = compute_bullet_display_name(
            "30 Cal .308 168 gr",  # stripping leaves nothing
            product_line="SpecialMatch",
            manufacturer_name="Hornady",
        )
        assert result == "SpecialMatch"

    def test_unknown_cartridge_format_returns_something(self):
        """A totally unfamiliar cartridge name should still produce output."""
        result = compute_cartridge_display_name(
            "MagicRound 7.62 NATO Special Purpose 175gr 2600fps",
            manufacturer_name="NewBrand",
        )
        assert result
        assert len(result) >= 2

    def test_empty_name_with_product_line(self):
        """Empty name but valid product_line should return product_line."""
        result = compute_bullet_display_name(
            "",
            product_line="MatchKing",
        )
        assert result == "MatchKing"

    def test_idempotency(self):
        """Running the cleaner twice produces the same output."""
        first = compute_bullet_display_name(
            "30 Cal .308 168 gr BTHP Match\u2122",
            manufacturer_name="Hornady",
        )
        second = compute_bullet_display_name(
            first,
            manufacturer_name="Hornady",
        )
        assert first == second

    def test_name_with_caliber_like_substring(self):
        """A product name containing caliber-like text shouldn't be destroyed."""
        result = compute_bullet_display_name(
            "30 Cal .308 168 gr SINGLE FEED Lazer-Tipped Hollow Point - 50ct",
            manufacturer_name="Cutting Edge Bullets",
        )
        assert "Lazer-Tipped Hollow Point" in result
