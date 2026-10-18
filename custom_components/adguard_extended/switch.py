"""Switch platform for AdGuard Home Extended."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up AdGuard Home Extended switches from a config entry."""
    coordinator = entry.runtime_data.state

    switches = [
        AdGuardFilteringSwitch(coordinator, entry),
        AdGuardYouTubeSwitch(coordinator, entry),
        AdGuardNintendoSwitch(coordinator, entry),
    ]

    async_add_entities(switches)


class AdGuardEntity(CoordinatorEntity[AdGuardHomeStateCoordinator], SwitchEntity):
    """Base entity for AdGuard Home Extended switches."""

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


class AdGuardFilteringSwitch(AdGuardEntity):
    """Switch to enable/disable DNS filtering."""

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize filtering switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_filtering_switch"
        self._attr_name = "Filtering"
        self._attr_icon = "mdi:filter-check"

    @property
    def is_on(self) -> bool:
        """Return true if filtering is enabled."""
        filtering = self.coordinator.data.get("filtering", {})
        return bool(filtering.get("enabled", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable filtering."""
        await self.coordinator.client.set_filtering(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable filtering."""
        await self.coordinator.client.set_filtering(False)
        await self.coordinator.async_request_refresh()


class AdGuardYouTubeSwitch(AdGuardEntity):
    """Switch to block/unblock YouTube."""

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize YouTube switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_youtube_block_switch"
        self._attr_name = "Block YouTube"
        self._attr_icon = "mdi:youtube"

    def _get_current_blocked(self) -> list[str]:
        """Extract blocked services list from coordinator data."""
        data = self.coordinator.data.get("blocked_services", [])
        if isinstance(data, list):
            return [str(item) for item in data]
        if isinstance(data, dict):
            return [str(item) for item in data.get("ids", [])]
        return []

    @property
    def is_on(self) -> bool:
        """Return true if YouTube is blocked."""
        return "youtube" in self._get_current_blocked()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Block YouTube (add to blocked services)."""
        current = self._get_current_blocked()
        if "youtube" not in current:
            current.append("youtube")
        await self.coordinator.client.set_blocked_services(current)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unblock YouTube (remove from blocked services)."""
        current = [s for s in self._get_current_blocked() if s != "youtube"]
        await self.coordinator.client.set_blocked_services(current)
        await self.coordinator.async_request_refresh()


class AdGuardNintendoSwitch(AdGuardEntity):
    """Switch to block/unblock Nintendo wildcard domains (*.nintendo.com and *.nintendo.net)."""

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, entry: AdGuardConfigEntry) -> None:
        """Initialize Nintendo wildcard rewrite switch."""
        super().__init__(coordinator, entry)
        self._domains = ["*.nintendo.com", "*.nintendo.net"]
        self._attr_unique_id = f"{entry.entry_id}_rewrite_nintendo_wildcards"
        self._attr_name = "Block Nintendo"
        self._attr_icon = "mdi:nintendo-switch"

    @property
    def is_on(self) -> bool:
        """Return true if both wildcard domains have active rewrites."""
        rewrites = self.coordinator.data.get("rewrites", [])
        if isinstance(rewrites, dict):
            rewrites = rewrites.get("data", [])
        existing_domains = {r.get("domain") for r in rewrites if isinstance(r, dict)}
        return all(d in existing_domains for d in self._domains)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Block both domains by adding DNS rewrites to 0.0.0.0."""
        rewrites = self.coordinator.data.get("rewrites", [])
        if isinstance(rewrites, dict):
            rewrites = rewrites.get("data", [])
        existing_domains = {r.get("domain") for r in rewrites if isinstance(r, dict)}

        for domain in self._domains:
            if domain not in existing_domains:
                await self.coordinator.client.add_rewrite(domain, "0.0.0.0")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unblock both domains by removing DNS rewrites."""
        rewrites = self.coordinator.data.get("rewrites", [])
        if isinstance(rewrites, dict):
            rewrites = rewrites.get("data", [])
        for r in rewrites:
            if isinstance(r, dict) and r.get("domain") in self._domains:
                await self.coordinator.client.delete_rewrite(r.get("domain"), r.get("answer", "0.0.0.0"))
        await self.coordinator.async_request_refresh()