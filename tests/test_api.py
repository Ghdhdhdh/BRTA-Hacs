"""Unit tests for the TROLS HTML parser, against real saved pages.

These only exercise custom_components/trols/api.py, which has no Home
Assistant dependency - just aiohttp (for the client) and BeautifulSoup. They
don't need a running Home Assistant to execute.
"""
from __future__ import annotations

import datetime
import pathlib

import pytest
from bs4 import BeautifulSoup

from custom_components.trols.api import (
    ParseError,
    TrolsClient,
    _extract_time,
    _normalise_team_label,
    _parse_trols_date,
)

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _soup(name: str) -> BeautifulSoup:
    return BeautifulSoup((FIXTURES / name).read_text(), "html.parser")


def test_normalise_team_label_strips_trailing_time():
    assert _normalise_team_label("BLTC\xa0Blue\xa0(8:00)") == "BLTC Blue"
    assert _normalise_team_label("Clarinda (10:00)") == "Clarinda"
    assert _normalise_team_label("Clarinda") == "Clarinda"


def test_parse_trols_date():
    assert _parse_trols_date("18 Jul 26") == datetime.date(2026, 7, 18)
    assert _parse_trols_date("") is None
    assert _parse_trols_date("not a date") is None


def test_extract_time():
    assert _extract_time("BLTC Blue (8:00)") == datetime.time(8, 0)
    assert _extract_time("Clarinda") is None


def test_select_options_daytime():
    soup = _soup("fixture_daytime.html")
    daytimes = TrolsClient._select_options(soup, "daytime")
    assert daytimes["AA"] == "Saturday AM - Spring 2026"
    assert daytimes["TN"] == "Tuesday Night - Spring 2026"
    assert "" not in daytimes  # blank placeholder option excluded


def test_select_options_section():
    soup = _soup("fixture_section.html")
    sections = TrolsClient._select_options(soup, "section")
    assert sections["AA018"] == "Rubbers 1"
    assert len(sections) == 17


def test_select_options_team():
    soup = _soup("fixture_team.html")
    teams = TrolsClient._select_options(soup, "team")
    assert teams == {
        "AA134": "BLTC Blue",
        "AA133": "BLTC White",
        "AA131": "Clarinda",
        "AA135": "Highmoor Uniting",
        "AA132": "Hurlingham Park",
        "AA136": "Kings Park",
        "AA137": "Royal Ave",
    }


def test_select_options_missing_select_raises():
    soup = BeautifulSoup("<html><body>nothing here</body></html>", "html.parser")
    with pytest.raises(ParseError):
        TrolsClient._select_options(soup, "daytime")


def test_parse_venues():
    soup = _soup("fixture_team.html")
    venues = TrolsClient._parse_venues(soup)
    assert venues["clarinda"].address == "4-14 Crawford Road, Clarinda"
    assert venues["clarinda"].latitude == pytest.approx(-37.9286)
    assert venues["clarinda"].longitude == pytest.approx(145.1019)
    assert venues["bltc blue"].address == venues["bltc white"].address


def test_parse_fixture_rows_for_home_and_away_matches():
    soup = _soup("fixture_team.html")
    venues = TrolsClient._parse_venues(soup)
    matches = TrolsClient._parse_fixture_rows(soup, "BLTC Blue", venues)

    # Byes (round 7 and 14) and "No Play" rows are not real matches.
    assert {m.round_label for m in matches} == {
        "1", "2", "3", "4", "5", "6", "8", "9", "10", "11", "12", "13",
    }

    round1 = next(m for m in matches if m.round_label == "1")
    assert round1.match_date == datetime.date(2026, 7, 18)
    assert round1.is_home is False
    assert round1.opponent == "BLTC White"
    assert round1.match_time == datetime.time(8, 0)
    assert round1.venue.name == "BLTC White"

    round2 = next(m for m in matches if m.round_label == "2")
    assert round2.is_home is True
    assert round2.opponent == "Highmoor Uniting"
    assert round2.venue.name == "BLTC Blue"


def test_parse_ladder_for_section():
    soup = _soup("ladders_section.html")
    entries = []
    for header_cell in soup.find_all("td", class_="sg"):
        link = header_cell.find("a")
        if link is None or "section=AA018" not in (link.get("href") or ""):
            continue
        table = header_cell.find_parent("table")
        rows = table.find_all("tr")[1:]
        position = 0
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            from custom_components.trols.api import _clean_text

            label = _normalise_team_label(_clean_text(cells[0]))
            if not label:
                continue
            position += 1
            entries.append((position, label))
        break

    assert entries[0] == (1, "BLTC Blue")
    assert entries[-1] == (7, "Clarinda")
    assert len(entries) == 7
