"""Sensor platform for TROLS: next match, ladder position, points, percentage."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ASSOCIATION_NAME,
    CONF_DAYTIME_NAME,
    CONF_SECTION_NAME,
    CONF_TEAM_NAME,
    DOMAIN,
)
from .coordinator import TrolsDataUpdateCoordinator, match_datetime


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the four TROLS sensors for a configured team."""
    coordinator: TrolsDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            TrolsNextMatchSensor(coordinator, entry),
            TrolsLadderPositionSensor(coordinator, entry),
            TrolsPointsSensor(coordinator, entry),
            TrolsPercentageSensor(coordinator, entry),
        ]
    )


class TrolsEntity(CoordinatorEntity[TrolsDataUpdateCoordinator]):
    """Shared device info for a configured team's entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: TrolsDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        data = entry.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=data[CONF_TEAM_NAME],
            manufacturer="TROLS",
            model=(
                f"{data[CONF_ASSOCIATION_NAME]} / {data[CONF_DAYTIME_NAME]} / "
                f"{data[CONF_SECTION_NAME]}"
            ),
        )


class TrolsNextMatchSensor(TrolsEntity, SensorEntity):
    """The team's next upcoming fixture, as a timestamp with match details."""

    _attr_translation_key = "next_match"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:tennis"

    def __init__(
        self, coordinator: TrolsDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_match"

    @property
    def native_value(self):
        match = self.coordinator.data.next_match if self.coordinator.data else None
        if match is None:
            return None
        return match_datetime(match)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        match = self.coordinator.data.next_match if self.coordinator.data else None
        if match is None:
            return {}
        venue = match.venue
        return {
            "opponent": match.opponent,
            "home_or_away": "home" if match.is_home else "away",
            "venue": venue.name if venue else None,
            "address": venue.address if venue else None,
            "latitude": venue.latitude if venue else None,
            "longitude": venue.longitude if venue else None,
            "round": match.round_label,
        }


class TrolsLadderPositionSensor(TrolsEntity, SensorEntity):
    """The team's current ladder position (1 = top of the ladder)."""

    _attr_translation_key = "ladder_position"
    _attr_icon = "mdi:format-list-numbered"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: TrolsDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_ladder_position"

    @property
    def native_value(self) -> int | None:
        entry = self.coordinator.data.ladder_entry if self.coordinator.data else None
        return entry.position if entry else None


class TrolsPointsSensor(TrolsEntity, SensorEntity):
    """The team's ladder points."""

    _attr_translation_key = "points"
    _attr_icon = "mdi:scoreboard-outline"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: TrolsDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_points"

    @property
    def native_value(self) -> float | None:
        entry = self.coordinator.data.ladder_entry if self.coordinator.data else None
        return entry.points if entry else None


class TrolsPercentageSensor(TrolsEntity, SensorEntity):
    """The team's ladder percentage (sets/games won vs lost ratio)."""

    _attr_translation_key = "percentage"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: TrolsDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_percentage"

    @property
    def native_value(self) -> float | None:
        entry = self.coordinator.data.ladder_entry if self.coordinator.data else None
        return entry.percentage if entry else None
