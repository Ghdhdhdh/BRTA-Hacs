"""Config flow for TROLS: association -> day/competition -> section -> club/team."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, ParseError, TrolsClient
from .const import (
    CONF_ASSOCIATION,
    CONF_ASSOCIATION_NAME,
    CONF_DAYTIME,
    CONF_DAYTIME_NAME,
    CONF_OTHER_ASSOCIATION,
    CONF_SECTION,
    CONF_SECTION_NAME,
    CONF_TEAM,
    CONF_TEAM_NAME,
    DOMAIN,
    KNOWN_ASSOCIATIONS,
)

_LOGGER = logging.getLogger(__name__)


class TrolsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Walk the user through association -> daytime -> section -> team."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}

    def _client(self, association: str) -> TrolsClient:
        return TrolsClient(async_get_clientsession(self.hass), association)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            association = user_input[CONF_ASSOCIATION]
            if association == CONF_OTHER_ASSOCIATION:
                return await self.async_step_association_other()
            self._data[CONF_ASSOCIATION] = association
            self._data[CONF_ASSOCIATION_NAME] = KNOWN_ASSOCIATIONS[association]
            return await self.async_step_daytime()

        options = {**KNOWN_ASSOCIATIONS, CONF_OTHER_ASSOCIATION: "Other (enter manually)"}
        schema = vol.Schema({vol.Required(CONF_ASSOCIATION): vol.In(options)})
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_association_other(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            association = user_input[CONF_ASSOCIATION].strip().lower()
            try:
                await self._client(association).async_get_daytimes()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except ParseError:
                errors["base"] = "invalid_association"
            else:
                self._data[CONF_ASSOCIATION] = association
                self._data[CONF_ASSOCIATION_NAME] = association.upper()
                return await self.async_step_daytime()

        schema = vol.Schema({vol.Required(CONF_ASSOCIATION): str})
        return self.async_show_form(
            step_id="association_other", data_schema=schema, errors=errors
        )

    async def async_step_daytime(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        try:
            daytimes = await self._client(
                self._data[CONF_ASSOCIATION]
            ).async_get_daytimes()
        except CannotConnect:
            return self.async_show_form(
                step_id="daytime",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )

        if user_input is not None and CONF_DAYTIME in user_input:
            daytime = user_input[CONF_DAYTIME]
            self._data[CONF_DAYTIME] = daytime
            self._data[CONF_DAYTIME_NAME] = daytimes[daytime]
            return await self.async_step_section()

        schema = vol.Schema({vol.Required(CONF_DAYTIME): vol.In(daytimes)})
        return self.async_show_form(step_id="daytime", data_schema=schema)

    async def async_step_section(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        try:
            sections = await self._client(self._data[CONF_ASSOCIATION]).async_get_sections(
                self._data[CONF_DAYTIME]
            )
        except CannotConnect:
            return self.async_show_form(
                step_id="section",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )

        if user_input is not None and CONF_SECTION in user_input:
            section = user_input[CONF_SECTION]
            self._data[CONF_SECTION] = section
            self._data[CONF_SECTION_NAME] = sections[section]
            return await self.async_step_team()

        schema = vol.Schema({vol.Required(CONF_SECTION): vol.In(sections)})
        return self.async_show_form(step_id="section", data_schema=schema)

    async def async_step_team(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        try:
            teams = await self._client(self._data[CONF_ASSOCIATION]).async_get_teams(
                self._data[CONF_DAYTIME], self._data[CONF_SECTION]
            )
        except CannotConnect:
            return self.async_show_form(
                step_id="team",
                data_schema=vol.Schema({}),
                errors={"base": "cannot_connect"},
            )

        if not teams:
            return self.async_abort(reason="no_teams")

        if user_input is not None and CONF_TEAM in user_input:
            team = user_input[CONF_TEAM]
            team_name = teams[team]

            await self.async_set_unique_id(
                f"{self._data[CONF_ASSOCIATION]}_{self._data[CONF_DAYTIME]}_"
                f"{self._data[CONF_SECTION]}_{team}"
            )
            self._abort_if_unique_id_configured()

            self._data[CONF_TEAM] = team
            self._data[CONF_TEAM_NAME] = team_name
            title = (
                f"{team_name} ({self._data[CONF_ASSOCIATION_NAME]} - "
                f"{self._data[CONF_DAYTIME_NAME]} - {self._data[CONF_SECTION_NAME]})"
            )
            return self.async_create_entry(title=title, data=self._data)

        schema = vol.Schema({vol.Required(CONF_TEAM): vol.In(teams)})
        return self.async_show_form(step_id="team", data_schema=schema)
