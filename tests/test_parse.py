"""Unit tests for the HTML-unescape step and field extraction.

Run with:  python -m pytest  (from the project root)
"""

from alerts.parse import (
    extract_fields,
    extract_min_odds,
    extract_odds,
    extract_stake,
    to_plain_text,
)

# The three sample bodies from the spec.
S1 = "Odds: [1.95] (only take it at 1.85 or better) Stake: 5 units"
S2 = "Odds: 2.19 Stake: 5 units (MAX BET)"
S3 = "Pick: Monaco ML and u4.5 goals- 1.9- 5U"


# --- HTML unescape / strip -------------------------------------------------

def test_to_plain_text_unescapes_and_strips_tags():
    raw = ("&lt;h1&gt;Pick of the Day&lt;/h1&gt;&lt;strong&gt;Odds:&lt;/strong&gt; "
           "[1.95] (only take it at 1.85 or better)&lt;br/&gt;Stake: 5 units")
    plain = to_plain_text(raw)
    assert "Odds:" in plain
    assert "Stake: 5 units" in plain
    assert "&lt;" not in plain and "<" not in plain          # no markup left
    assert "1.85" in plain


def test_to_plain_text_handles_double_escaping_and_empty():
    assert to_plain_text("") == ""
    assert to_plain_text(None) == ""
    double = "&amp;lt;strong&amp;gt;Odds: 2.0&amp;lt;/strong&amp;gt;"
    assert "Odds: 2.0" in to_plain_text(double)


# --- odds ------------------------------------------------------------------

def test_extract_odds():
    assert extract_odds(S1) == 1.95
    assert extract_odds(S2) == 2.19
    # Loose format: 1.9 is the price; the u4.5 total must NOT be picked.
    assert extract_odds(S3) == 1.9


# --- stake -----------------------------------------------------------------

def test_extract_stake():
    assert extract_stake(S1) == 5
    assert extract_stake(S2) == 5
    assert extract_stake(S3) == 5          # "5U"


# --- minimum acceptable odds ----------------------------------------------

def test_extract_min_odds():
    assert extract_min_odds(S1) == 1.85
    assert extract_min_odds(S2) is None
    assert extract_min_odds(S3) is None


def test_extract_min_odds_dont_take_below_phrasing():
    assert extract_min_odds("Odds: 2.0 Stake: 3 units. Don't take it below 1.9") == 1.9


# --- combined --------------------------------------------------------------

def test_extract_fields_combined():
    f = extract_fields(S1)
    assert (f.odds, f.stake, f.min_odds) == (1.95, 5, 1.85)
    f3 = extract_fields(S3)
    assert (f3.odds, f3.stake) == (1.9, 5)
    assert f3.pick == "Monaco ML and u4.5 goals- 1.9- 5U"
