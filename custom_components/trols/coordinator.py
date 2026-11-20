"""Data update coordinator for the TROLS integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, LadderEntry, Match, ParseError, TrolsClient
from .const import (
    CONF_DAYTIME,
    CONF_SECTION,
    CONF_TEAM,
    CONF_TEAM_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MELBOURNE_TZ = ZoneInfo("Australia/Melbourne")


@dataclass
class TrolsData:
    """Combined ladder + fixture data for one configured team."""

    ladder_entry: LadderEntry | None
    next_match: Match | None


class TrolsDataUpdateCoordinator(DataUpdateCoordinator[TrolsData]):
    """Polls TROLS for one configured team's ladder position and draw."""

    def __init__(
        self, hass: HomeAssistant, client: TrolsClient, entry: ConfigEntry
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._client = client
        self._entry = entry

    async def _async_update_data(self) -> TrolsData:
        data = self._entry.data
        daytime = data[CONF_DAYTIME]
        section = data[CONF_SECTION]
        team = data[CONF_TEAM]
        team_name = data[CONF_TEAM_NAME]

        try:
            ladder = await self._client.async_get_ladder(daytime, section)
            matches = await self._client.async_get_fixture(
                daytime, section, team, team_name
            )
        except CannotConnect as err:
            raise UpdateFailed(f"Could not reach trols.org.au: {err}") from err
        except ParseError as err:
            raise UpdateFailed(f"Unexpected TROLS page layout: {err}") from err

        return TrolsData(
            ladder_entry=_find_ladder_entry(ladder, team_name),
            next_match=_find_next_match(matches),
        )


def _find_ladder_entry(
    entries: list[LadderEntry], team_label: str
) -> LadderEntry | None:
    target = team_label.strip().lower()
    for entry in entries:
        if entry.team_label.strip().lower() == target:
            return entry
    return None


def _find_next_match(matches: list[Match]) -> Match | None:
    today = datetime.now(MELBOURNE_TZ).date()
    upcoming = [m for m in matches if m.match_date >= today]
    if not upcoming:
        return None
    return min(upcoming, key=lambda m: m.match_date)


def match_datetime(match: Match) -> datetime:
    """Combine a match's date and (if known) start time into an aware datetime.

    The time comes from whichever team is listed as "Home" for that round
    (its club's standard start time for the section), taken as-is from the
    page. Falls back to midnight (date only) when no start time was found.
    """
    time_ = match.match_time or datetime.min.time()
    return datetime.combine(match.match_date, time_, tzinfo=MELBOURNE_TZ)
