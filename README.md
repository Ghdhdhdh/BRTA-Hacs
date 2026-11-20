# TROLS Tennis Ladder for Home Assistant

A [HACS](https://hacs.xyz/) custom integration that scrapes
[trols.org.au](https://trols.org.au) - the online competition system used by
dozens of suburban tennis associations around Melbourne (BRTA, WDTA, MDJTA,
HDTA, and more) - and exposes your club's ladder position and next fixture
as Home Assistant entities.

TROLS has no public API; this integration works by replaying the same
form submissions a browser makes when you click through
Association -> Competition -> Section -> Team on the TROLS website, then
parsing the resulting HTML.

## Installation

### HACS (custom repository)

1. HACS -> Integrations -> the "..." menu (top right) -> **Custom repositories**.
2. Add this repository's URL, category **Integration**.
3. Install "TROLS Tennis Ladder", then restart Home Assistant.

### Manual

Copy `custom_components/trols` into your Home Assistant `config/custom_components/` directory and restart.

## Setup

Settings -> Devices & Services -> Add Integration -> **TROLS Tennis Ladder**.

You'll be asked, in order:

1. **Association** - e.g. BRTA, WDTA, HDTA. If yours isn't in the list, choose "Other" and type its TROLS code (the short path trols.org.au uses, e.g. `brta` for `https://trols.org.au/brta/`).
2. **Competition** - the day/time competition (e.g. "Saturday AM - Spring 2026").
3. **Section** - your grade/section within that competition.
4. **Club / Team** - your team. Clubs with more than one team in a section (e.g. "Blue" / "White") are listed as separate entries.

Each configured team becomes one device with four entities:

| Entity | What it is |
| --- | --- |
| **Next match** | A timestamp sensor: the date/time of your team's next fixture. Attributes: `opponent`, `home_or_away`, `venue`, `address`, `latitude`, `longitude`, `round`. |
| **Ladder position** | Your team's current rank in its section (1 = top). |
| **Points** | Ladder points. |
| **Percentage** | Ladder percentage. |

Data refreshes every 30 minutes.

## Known limitations

- **Finals**: TROLS only lists a generic "Semi Final" / "Grand Final" date for a section once the regular season ends - it doesn't say who plays whom until the draw is seeded. The "Next match" sensor only looks at the regular-season draw, so once your last regular-season round has passed, it will show no upcoming match even if a final is coming up.
- **Match time**: the time shown next to a round is whatever home-ground start time TROLS prints for that round's home team (e.g. "8:00"). TROLS doesn't mark AM/PM/night on this page, so the sensor uses the value as printed; for an evening competition, check the actual time against the TROLS website if in doubt.
- Built and tested against BRTA's pages (Saturday AM comp). Other associations use the same TROLS software and page layout, but if your association's pages differ, the ladder/fixture parsing may need small tweaks - please open an issue with the association code if something doesn't load.

## Development

```
pip install beautifulsoup4 aiohttp pytest
pytest tests/test_api.py
```

`tests/fixtures/*.html` are real pages captured from `trols.org.au/brta/` and are what the parser is tested against (see `tests/test_api.py`). `conftest.py` loads `const.py`/`api.py` directly so they can be tested without a full Home Assistant install - `config_flow.py`, `coordinator.py`, `sensor.py` and `__init__.py` depend on Home Assistant itself and aren't covered by these tests; verifying those needs a real (or `pytest-homeassistant-custom-component`-backed) Home Assistant instance.
