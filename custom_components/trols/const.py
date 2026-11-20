"""Constants for the TROLS integration."""
from datetime import timedelta

DOMAIN = "trols"

BASE_URL = "https://trols.org.au"

CONF_ASSOCIATION = "association"
CONF_DAYTIME = "daytime"
CONF_SECTION = "section"
CONF_TEAM = "team"

CONF_ASSOCIATION_NAME = "association_name"
CONF_DAYTIME_NAME = "daytime_name"
CONF_SECTION_NAME = "section_name"
CONF_TEAM_NAME = "team_name"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# Associations known to run on trols.org.au, scraped from
# https://trols.org.au/mobile/index.php. Not exhaustive: the config flow
# also lets the user type any other association's URL path directly, since
# TROLS adds new associations over time.
KNOWN_ASSOCIATIONS: dict[str, str] = {
    "brta": "BRTA - Bayside Region Tennis",
    "bdta": "BDTA - Berwick & District Junior Tennis",
    "bdnta": "BDNTA - Blackburn & District Night Tennis",
    "dvta": "DVTA - Diamond Valley Tennis",
    "erta": "ERTA - Eastern Region Tennis",
    "hdta": "HDTA - Heidelberg & Districts Tennis",
    "ldnta": "LDNTA - Lilydale & Districts Night Tennis",
    "metro": "Metro Masters Tennis",
    "nejta": "NEJTA - North Eastern Junior Tennis",
    "nentg": "NENTG - North Eastern Night Tennis Group",
    "wdta": "WDTA - Waverley Tennis",
}

CONF_OTHER_ASSOCIATION = "__other__"
