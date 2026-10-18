"""Data update coordinators for AdGuard Home."""

from abc import abstractmethod
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from typing import override

from adguardhome import (
    AdGuardHome,
    AdGuardHomeError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

type AdGuardConfigEntry = ConfigEntry[AdGuardData]


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeState:
    """The status of AdGuard Home and the features that can be turned on and off."""

    status: Any
    filtering: Any
    parental: bool
    query_log: Any
    safe_browsing: bool
    safe_search: Any
    blocked_services: list[str]
    rewrites: list[dict]

@dataclass(frozen=True, kw_only=True)
class AdGuardHomeStatistics:
    """The statistics of AdGuard Home, and its blocklists."""

    stats: Any
    blocklists: tuple[Any, ...]


class AdGuardHomeCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base for the coordinators of AdGuard Home."""

    config_entry: AdGuardConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: AdGuardConfigEntry,
        client: AdGuardHome,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{name}",
            update_interval=update_interval,
        )
        self.client = client
        
    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch the data from AdGuard Home."""
        try:
            return await self._async_fetch()
        except AdGuardHomeError as error:
            # Si l'erreur contient un problème d'authentification (souvent 401/403)
            if "auth" in str(error).lower() or "unauthorized" in str(error).lower():
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="authentication_failed",
                ) from error
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(error)},
            ) from error

    @abstractmethod
    async def _async_fetch(self) -> _DataT:
        """Fetch the data of this coordinator from AdGuard Home."""


class AdGuardHomeStateCoordinator(AdGuardHomeCoordinator[AdGuardHomeState]):
    """Keep track of what is turned on in AdGuard Home."""

    def __init__(
        self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardHome
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client, "state", timedelta(seconds=10))

    @override
    async def _async_fetch(self) -> AdGuardHomeState:
        """Fetch the status and settings of AdGuard Home."""
        (
            status,
            filtering,
            parental,
            query_log,
            safe_browsing,
            safe_search,
            blocked_services_response,
            rewrites_response,
        ) = await asyncio.gather(
            self.client.status(),
            self.client.filtering.config(),
            self.client.parental.enabled(),
            self.client.querylog.config(),
            self.client.safebrowsing.enabled(),
            self.client.safesearch.config(),
            self.client._request("control/blocked_services/get"),
            self.client._request("control/rewrite/list"),
        )

        blocked_services = blocked_services_response.get("apps", []) if isinstance(blocked_services_response, dict) else []
        rewrites = rewrites_response if isinstance(rewrites_response, list) else []

        return AdGuardHomeState(
            status=status,
            filtering=filtering,
            parental=parental,
            query_log=query_log,
            safe_browsing=safe_browsing,
            safe_search=safe_search,
            blocked_services=blocked_services,
            rewrites=rewrites,
        )

    async def async_set_dns_rewrite_status(self, target_domain: str, enabled: bool) -> None:
        """Active ou desactive une reecriture DNS existante par son domaine."""
        rewrites = await self.client._request("control/rewrite/list")
        
        rule_to_update = None
        for rule in rewrites:
            if rule.get("domain") == target_domain:
                rule_to_update = rule
                break
        
        if rule_to_update:
            await self.client._request(
                "control/rewrite/update",
                method="PUT",
                json={
                    "target": {
                        "domain": rule_to_update.get("domain"),
                        "answer": rule_to_update.get("answer"),
                    },
                    "update": {
                        "domain": rule_to_update.get("domain"),
                        "answer": rule_to_update.get("answer"),
                        "enabled": enabled,
                    }
                },
            )
            await self.async_request_refresh()


class AdGuardHomeStatisticsCoordinator(AdGuardHomeCoordinator[AdGuardHomeStatistics]):
    """Keep track of the statistics of AdGuard Home."""

    def __init__(
        self, hass: HomeAssistant, entry: AdGuardConfigEntry, client: AdGuardHome
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, entry, client, "statistics", timedelta(minutes=5))

    @override
    async def _async_fetch(self) -> AdGuardHomeStatistics:
        """Fetch the statistics and blocklists of AdGuard Home."""
        stats, blocklists = await asyncio.gather(
            self.client.stats.get(),
            self.client.filtering.blocklists.list(),
        )

        return AdGuardHomeStatistics(stats=stats, blocklists=blocklists)

@dataclass
class AdGuardData:
    """Data of an AdGuard Home config entry."""

    client: AdGuardHome
    state: AdGuardHomeStateCoordinator
    statistics: AdGuardHomeStatisticsCoordinator
    # update: AdGuardHomeUpdateCoordinator
