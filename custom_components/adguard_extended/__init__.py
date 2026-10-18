"""Support for AdGuard Home Extended."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import AdGuardClient, AdGuardConfigEntry, AdGuardData, AdGuardHomeStateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR, Platform.SWITCH]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Set up AdGuard Home Extended from a config entry."""
    client = AdGuardClient(hass, entry.data)
    state_coordinator = AdGuardHomeStateCoordinator(hass, entry, client)

    await state_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AdGuardData(
        client=client,
        state=state_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdGuardConfigEntry) -> bool:
    """Unload AdGuard Home Extended config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)