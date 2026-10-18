"""Sensor platform for AdGuard Home Extended."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AdGuardConfigEntry, AdGuardHomeStateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up AdGuard Home Extended sensors from a config entry."""
    coordinator = entry.runtime_data.state

    sensors = [
        AdGuardProtectionSensor(coordinator, entry),
        AdGuardFilteringSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class AdGuardEntity(CoordinatorEntity[AdGuardHomeStateCoordinator], SensorEntity):
    """Base entity for AdGuard Home Extended."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="AdGuard Home",
            model="Extended API",
        )


class AdGuardProtectionSensor(AdGuardEntity):
    """Representation of AdGuard Protection Status Sensor."""

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize protection sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_protection_status"
        self._attr_name = "Protection Status"
        self._attr_icon = "mdi:shield-check"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        status = self.coordinator.data.get("status", {})
        return "Enabled" if status.get("protection_enabled", False) else "Disabled"


class AdGuardFilteringSensor(AdGuardEntity):
    """Representation of AdGuard Filtering Enabled Sensor."""

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize filtering sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_filtering_status"
        self._attr_name = "Filtering Status"
        self._attr_icon = "mdi:filter"

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        filtering = self.coordinator.data.get("filtering", {})
        return "Enabled" if filtering.get("enabled", False) else "Disabled"