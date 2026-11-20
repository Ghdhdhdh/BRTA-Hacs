"""Async scraper client for trols.org.au.

TROLS has no public API - every association's ladders, fixtures and team
lists are rendered as plain HTML forms. The forms POST back to the same
page with a `which` field telling the server which <select> was just
changed, so a full "walk" through association -> day/competition ->
section -> team is just a sequence of GET/POST requests against
`fixture.php` (for the team list and the draw) and `ladders.php` (for the
ladder position/points/percentage).

All parsing here is based on real pages fetched from
https://trols.org.au/brta/ during development (see tests/fixtures/).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time

from aiohttp import ClientError, ClientSession
from bs4 import BeautifulSoup, Tag

from .const import BASE_URL

_NBSP = "\xa0"
_PAREN_TIME_RE = re.compile(r"\((\d{1,2}):(\d{2})\)")
_TRAILING_PAREN_RE = re.compile(r"\s*\([^)]*\)\s*$")


class TrolsError(Exception):
    """Base error for anything that goes wrong talking to TROLS."""


class CannotConnect(TrolsError):
    """Raised when the HTTP request itself fails."""


class ParseError(TrolsError):
    """Raised when a page doesn't look like what we expected."""


@dataclass
class LadderEntry:
    """One team's row on a ladder."""

    position: int
    team_label: str
    won: float | None
    points: float | None
    percentage: float | None


@dataclass
class VenueInfo:
    """A team's home venue, as listed in a fixture page's section info."""

    name: str
    address: str | None
    latitude: float | None
    longitude: float | None


@dataclass
class Match:
    """A single fixture row for the section the selected team plays in."""

    round_label: str | None
    match_date: date
    match_time: dt_time | None
    is_home: bool
    opponent: str
    venue: VenueInfo | None


def _clean_text(tag: Tag | None) -> str:
    """Get a tag's visible text with &nbsp; turned into normal spaces."""
    if tag is None:
        return ""
    return tag.get_text(_NBSP).replace(_NBSP, " ").strip()


def _normalise_team_label(text: str) -> str:
    """Strip a trailing "(8:00)" style start-time suffix and collapse spaces."""
    text = _TRAILING_PAREN_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


class TrolsClient:
    """Scrapes a single TROLS association."""

    def __init__(self, session: ClientSession, association: str) -> None:
        self._session = session
        self._association = association.strip().lower()
        self._base = f"{BASE_URL}/{self._association}"

    async def _fetch(self, page: str, data: dict[str, str] | None = None) -> BeautifulSoup:
        url = f"{self._base}/{page}"
        try:
            if data is None:
                async with self._session.get(url, timeout=20) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
            else:
                async with self._session.post(url, data=data, timeout=20) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
        except (ClientError, TimeoutError) as err:
            raise CannotConnect(f"Could not reach {url}: {err}") from err
        return BeautifulSoup(text, "html.parser")

    @staticmethod
    def _select_options(soup: BeautifulSoup, select_id: str) -> dict[str, str]:
        select = soup.find("select", id=select_id)
        if select is None:
            raise ParseError(f"Could not find the '{select_id}' selector on the page")
        options: dict[str, str] = {}
        for option in select.find_all("option"):
            value = (option.get("value") or "").strip()
            if not value:
                continue
            options[value] = _clean_text(option)
        return options

    async def async_get_daytimes(self) -> dict[str, str]:
        """Return {daytime_code: label} e.g. {"AA": "Saturday AM - Spring 2026"}."""
        soup = await self._fetch("fixture.php")
        return self._select_options(soup, "daytime")

    async def async_get_sections(self, daytime: str) -> dict[str, str]:
        """Return {section_code: label} for a given competition/daytime."""
        soup = await self._fetch(
            "fixture.php", {"which": "0", "style": "", "daytime": daytime}
        )
        return self._select_options(soup, "section")

    async def async_get_teams(self, daytime: str, section: str) -> dict[str, str]:
        """Return {team_code: label} e.g. {"AA134": "BLTC Blue"} for a section."""
        soup = await self._fetch(
            "fixture.php",
            {"which": "1", "style": "", "daytime": daytime, "section": section},
        )
        return self._select_options(soup, "team")

    async def async_get_ladder(self, daytime: str, section: str) -> list[LadderEntry]:
        """Return the ladder for one section, in position order (top first)."""
        soup = await self._fetch(
            "ladders.php",
            {"which": "1", "style": "", "daytime": daytime, "section": section},
        )
        # The ladder tables share a distinctive header row: a bold section-name
        # link, then "Won", "Pts", "%". There may be several such tables on
        # the page if the site decides to also show a neighbouring section,
        # so match on the section code embedded in the header link's href.
        entries: list[LadderEntry] = []
        for header_cell in soup.find_all("td", class_="sg"):
            link = header_cell.find("a")
            if link is None or f"section={section}" not in (link.get("href") or ""):
                continue
            table = header_cell.find_parent("table")
            if table is None:
                continue
            rows = table.find_all("tr")[1:]  # skip header row
            position = 0
            for row in rows:
                cells = row.find_all("td")
                if len(cells) < 4:
                    continue
                label = _normalise_team_label(_clean_text(cells[0]))
                if not label:
                    continue
                position += 1
                entries.append(
                    LadderEntry(
                        position=position,
                        team_label=label,
                        won=_parse_float(_clean_text(cells[1])),
                        points=_parse_float(_clean_text(cells[2])),
                        percentage=_parse_float(_clean_text(cells[3])),
                    )
                )
            break
        if not entries:
            raise ParseError(
                f"Could not find a ladder table for section '{section}'"
            )
        return entries

    async def async_get_fixture(
        self, daytime: str, section: str, team: str, team_label: str
    ) -> list[Match]:
        """Return the draw for one team, with venues filled in.

        `team_label` must be the label TROLS uses for this team (as returned
        by `async_get_teams`), e.g. "BLTC Blue" - it's used to work out which
        side of each Home/Away row is "us".
        """
        soup = await self._fetch(
            "fixture.php",
            {
                "which": "2",
                "style": "",
                "daytime": daytime,
                "section": section,
                "team": team,
            },
        )
        venues = self._parse_venues(soup)
        return self._parse_fixture_rows(soup, team_label, venues)

    @staticmethod
    def _parse_venues(soup: BeautifulSoup) -> dict[str, VenueInfo]:
        """Parse the "Section Information" table: team -> home venue."""
        venues: dict[str, VenueInfo] = {}
        header = soup.find("td", string=re.compile("Section Information"))
        if header is None:
            return venues
        table = header.find_parent("table")
        if table is None:
            return venues
        rows = table.find_all("tr")
        i = 0
        while i < len(rows):
            cells = rows[i].find_all("td")
            if len(cells) == 3 and _clean_text(cells[0]):
                label = _normalise_team_label(_clean_text(cells[1]))
                map_link = cells[2].find("a")
                lat = lon = None
                if map_link is not None:
                    match = re.search(
                        r"pop_map\('[^']*',\s*(-?[\d.]+),\s*(-?[\d.]+)",
                        map_link.get("onclick") or "",
                    )
                    if match:
                        lat, lon = float(match.group(1)), float(match.group(2))
                address = None
                if i + 1 < len(rows):
                    addr_cells = rows[i + 1].find_all("td")
                    if len(addr_cells) >= 2:
                        address = _clean_text(addr_cells[1]).replace("\n", ", ") or None
                if label:
                    venues[label.lower()] = VenueInfo(
                        name=label, address=address, latitude=lat, longitude=lon
                    )
            i += 1
        return venues

    @staticmethod
    def _parse_fixture_rows(
        soup: BeautifulSoup, team_label: str, venues: dict[str, VenueInfo]
    ) -> list[Match]:
        """Parse the Rd/Date/Home/Away draw table for one team.

        Rows where either side is "Bye" or that say "No Play" aren't real
        matches, so they're left out of the returned list.

        TROLS pages nest a <table> inside a <td> without a closing tag the
        parser can rely on, which makes Python's HTML parsers duplicate the
        header row into outer tables and lose sibling relationships. So
        instead of walking siblings from a <th> row, we find the table via
        its distinctive "Fixture for ..." caption cell and walk its direct
        child rows, which parse reliably.
        """
        caption = None
        for td in soup.find_all("td", class_="mg"):
            if "Fixture for" in td.get_text():
                caption = td
                break
        if caption is None:
            raise ParseError("Could not find the fixture draw table")
        table = caption.find_parent("table")
        if table is None:
            raise ParseError("Could not find the fixture draw table")
        rows = table.find_all("tr", recursive=False)
        our_label = _normalise_team_label(team_label).lower()
        matches: list[Match] = []
        for row in rows:
            # Skip the caption row and the header row; stop once we hit the
            # finals block, which is a nested <table> inside its own <tr>.
            if row.find("th") is not None or row.find("table") is not None:
                continue
            cells = row.find_all("td", recursive=False)
            if len(cells) < 4:
                continue
            date_text = _clean_text(cells[1])
            match_date = _parse_trols_date(date_text)
            if match_date is None:
                continue
            home_text = _clean_text(cells[2])
            away_text = _clean_text(cells[3])
            if "no play" in home_text.lower():
                continue
            home_label = _normalise_team_label(home_text)
            away_label = _normalise_team_label(away_text)
            if home_label.lower() == "bye" or away_label.lower() == "bye":
                continue
            is_home = home_label.lower() == our_label
            opponent = away_label if is_home else home_label
            matches.append(
                Match(
                    round_label=_clean_text(cells[0]) or None,
                    match_date=match_date,
                    match_time=_extract_time(home_text),
                    is_home=is_home,
                    opponent=opponent,
                    venue=venues.get(home_label.lower()),
                )
            )
        return matches


def _parse_float(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_trols_date(text: str) -> date | None:
    """Parse TROLS' "18 Jul 26" style date. Returns None for blank cells."""
    text = text.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d %b %y").date()
    except ValueError:
        return None


def _extract_time(cell_text: str) -> dt_time | None:
    match = _PAREN_TIME_RE.search(cell_text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return dt_time(hour=hour, minute=minute)
