"""Data update coordinator using direct HTTP requests for AdGuard Home Extended."""

import asyncio
from datetime import timedelta
from typing import Any

from aiohttp import BasicAuth
from yarl import URL

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AdGuardConfigEntry = ConfigEntry[AdGuardData]


class AdGuardClient:
    """Minimal direct API client for AdGuard Home."""

    def __init__(self, hass: HomeAssistant, entry_data: dict[str, Any]) -> None:
        self.hass = hass
        self.ssl = entry_data[CONF_SSL]
        self.host = entry_data[CONF_HOST]
        self.port = entry_data[CONF_PORT]
        self.verify_ssl = entry_data[CONF_VERIFY_SSL]
        self.username = entry_data.get(CONF_USERNAME)
        self.password = entry_data.get(CONF_PASSWORD)
        self.session = async_get_clientsession(hass, self.verify_ssl)

    async def request(self, path: str, method: str = "GET", json: dict | list | None = None) -> Any:
        """Perform an HTTP request to AdGuard Home API."""
        scheme = "https" if self.ssl else "http"
        url = URL.build(scheme=scheme, host=self.host, port=self.port).with_path(path)
        auth = BasicAuth(self.username, self.password) if self.username and self.password else None

        try:
            async with self.session.request(method, url, auth=auth, json=json, timeout=10) as resp:
                if resp.status in (401, 403):
                    raise ConfigEntryAuthFailed("Authentication failed")
                if resp.status != 200:
                    raise UpdateFailed(f"HTTP error {resp.status} on {path}")
                if resp.content_type == "application/json":
                    return await resp.json()
                return await resp.text()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with AdGuard Home: {err}") from err

    async def set_filtering(self, enabled: bool) -> None:
        """Enable or disable filtering."""
        filtering = await self.request("/control/filtering/status")
        if isinstance(filtering, dict):
            filtering["enabled"] = enabled
            await self.request("/control/filtering/config", method="POST", json=filtering)

    async def set_blocked_services(self, ids: list[str]) -> None:
        """Set blocked services ids."""
        await self.request("/control/blocked_services/set", method="POST", json=ids)

    async def add_rewrite(self, domain: str, answer: str) -> None:
        """Add a DNS rewrite rule."""
        await self.request("/control/rewrite/add", method="POST", json={"domain": domain, "answer": answer})

    async def delete_rewrite(self, domain: str, answer: str) -> None:
        """Delete a DNS rewrite rule."""
        await self.request("/control/rewrite/delete", method="POST", json={"domain": domain, "answer": answer})


class AdGuardHomeStateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to fetch status, filtering, rewrites, and blocked services."""

    def __init__(self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardClient) -> None:
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_state",
            update_interval=timedelta(seconds=10),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch status, filtering, rewrites, and blocked services data."""
        status, filtering, rewrites, blocked_services = await asyncio.gather(
            self.client.request("/control/status"),
            self.client.request("/control/filtering/status"),
            self.client.request("/control/rewrite/list"),
            self.client.request("/control/blocked_services/list"),
        )
        return {
            "status": status,
            "filtering": filtering,
            "rewrites": rewrites,
            "blocked_services": blocked_services,
        }


class AdGuardData:
    """Data stored in runtime_data."""

    def __init__(self, client: AdGuardClient, state: AdGuardHomeStateCoordinator) -> None:
        self.client = client
        self.state = state