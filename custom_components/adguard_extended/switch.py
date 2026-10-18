"""Support for AdGuard Home switches."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from adguardhome import AdGuardHome, AdGuardHomeError

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    AdGuardConfigEntry,
    AdGuardHomeState,
    AdGuardHomeStateCoordinator,
)
from .entity import AdGuardHomeEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AdGuardHomeSwitchEntityDescription(SwitchEntityDescription):
    """Describes AdGuard Home switch entity."""

    is_on_fn: Callable[[AdGuardHomeState], bool]
    turn_on_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]
    turn_off_fn: Callable[[AdGuardHome], Callable[[], Coroutine[Any, Any, None]]]


SWITCHES: tuple[AdGuardHomeSwitchEntityDescription, ...] = (
    AdGuardHomeSwitchEntityDescription(
        key="protection",
        translation_key="protection",
        is_on_fn=lambda data: data.status.protection_enabled,
        turn_on_fn=lambda adguard: adguard.enable_protection,
        turn_off_fn=lambda adguard: adguard.disable_protection,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="parental",
        translation_key="parental",
        is_on_fn=lambda data: data.parental,
        turn_on_fn=lambda adguard: adguard.parental.enable,
        turn_off_fn=lambda adguard: adguard.parental.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safesearch",
        translation_key="safe_search",
        is_on_fn=lambda data: data.safe_search.enabled,
        turn_on_fn=lambda adguard: adguard.safesearch.enable,
        turn_off_fn=lambda adguard: adguard.safesearch.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="safebrowsing",
        translation_key="safe_browsing",
        is_on_fn=lambda data: data.safe_browsing,
        turn_on_fn=lambda adguard: adguard.safebrowsing.enable,
        turn_off_fn=lambda adguard: adguard.safebrowsing.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="filtering",
        translation_key="filtering",
        is_on_fn=lambda data: data.filtering.enabled,
        turn_on_fn=lambda adguard: adguard.filtering.enable,
        turn_off_fn=lambda adguard: adguard.filtering.disable,
    ),
    AdGuardHomeSwitchEntityDescription(
        key="querylog",
        translation_key="query_log",
        is_on_fn=lambda data: data.query_log.enabled,
        turn_on_fn=lambda adguard: adguard.querylog.enable,
        turn_off_fn=lambda adguard: adguard.querylog.disable,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdGuardConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up AdGuard Home switch based on a config entry."""
    coordinator = entry.runtime_data.state

    # Liste des domaines DNS à contrôler via un switch
    nintendo_domains = ["*.nintendo.com", "*.nintendo.net"]

    # Création de la liste des entités
    entities = [
        AdGuardYouTubeSwitch(coordinator),
    ]

    # Ajout des interrupteurs DNS Nintendo
    for domain in nintendo_domains:
        entities.append(AdGuardDNSRewriteSwitch(coordinator, domain))

    # Ajout des interrupteurs par défaut d'AdGuard
    entities.extend(
        AdGuardHomeSwitch(coordinator, description) for description in SWITCHES
    )

    # Enregistrement de toutes les entités en une seule fois
    async_add_entities(entities) for description in SWITCHES
        
#async_add_entities(
#        [AdGuardYouTubeSwitch(coordinator)]
#        + [
#            AdGuardHomeSwitch(coordinator, description)
#            for description in SWITCHES
#        ]
#    )


class AdGuardHomeSwitch(AdGuardHomeEntity[AdGuardHomeStateCoordinator], SwitchEntity):
    """Defines a AdGuard Home switch."""

    entity_description: AdGuardHomeSwitchEntityDescription

    def __init__(
        self,
        coordinator: AdGuardHomeStateCoordinator,
        description: AdGuardHomeSwitchEntityDescription,
    ) -> None:
        """Initialize AdGuard Home switch."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        try:
            await self.entity_description.turn_off_fn(self.coordinator.client)()
        except AdGuardHomeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_while_turn_off",
            ) from err

        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.entity_description.turn_on_fn(self.coordinator.client)()
        except AdGuardHomeError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="error_while_turn_on",
            ) from err

        await self.coordinator.async_request_refresh()

    @property
    @override
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.is_on_fn(self.coordinator.data)


# Ajoutez ou intégrez cette classe dans switch.py

class AdGuardYouTubeSwitch(AdGuardHomeEntity[AdGuardHomeStateCoordinator], SwitchEntity):
    """Représente un interrupteur pour bloquer ou autoriser YouTube."""

    _attr_icon = "mdi:youtube"

    def __init__(self, coordinator: AdGuardHomeStateCoordinator) -> None:
        """Initialisation de l'interrupteur YouTube."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_blocked_service_youtube"
        self._attr_name = "YouTube"  # Ou "AdGuard YouTube Block" selon vos préférences
        self.translation_key = "blocked_services_youtube"  
        
    @property
    @override
    def is_on(self) -> bool:
        """Retourne True si YouTube est présent dans la liste des services bloqués."""
        blocked_services = self.coordinator.data.blocked_services
        return "youtube" in blocked_services

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active le blocage de YouTube."""
        current_services = list(self.coordinator.data.blocked_services)
        if "youtube" not in current_services:
            current_services.append("youtube")
        
        # Appel direct à l'API AdGuard pour mettre à jour les services bloqués
        await self.coordinator.client._request(
            "control/blocked_services/set",
            method="POST",
            json={"apps": current_services},
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive le blocage de YouTube (autorise YouTube)."""
        current_services = list(self.coordinator.data.blocked_services)
        if "youtube" in current_services:
            current_services.remove("youtube")
        
        # Appel direct à l'API AdGuard pour mettre à jour les services bloqués
        await self.coordinator.client._request(
            "control/blocked_services/set",
            method="POST",
            json={"apps": current_services},
        )
        await self.coordinator.async_request_refresh()
        
class AdGuardDNSRewriteSwitch(AdGuardHomeEntity[AdGuardHomeStateCoordinator], SwitchEntity):
    """Interrupteur pour activer ou désactiver une réécriture DNS AdGuard."""

    _attr_icon = "mdi:nintendo-switch"

    def __init__(self, coordinator: AdGuardHomeStateCoordinator, domain: str) -> None:
        """Initialisation du switch pour un domaine donné."""
        super().__init__(coordinator)
        self._domain = domain
        entry = coordinator.config_entry
        
        # Identifiant unique basé sur le domaine (ex: adguard_dns_rewrite_nintendo_com)
        clean_domain = domain.replace("*.", "").replace(".", "_")
        self._attr_unique_id = f"{entry.entry_id}_dns_rewrite_{clean_domain}"
        self._attr_name = f"DNS Rewrite {domain}"

    @property
    @override
    def is_on(self) -> bool:
        """Retourne True si la règle DNS existe et est activée (enabled: True)."""
        rewrites = self.coordinator.data.rewrites
        for rule in rewrites:
            if rule.get("domain") == self._domain:
                return rule.get("enabled", True)
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Active la réécriture DNS."""
        await self.coordinator.async_set_dns_rewrite_status(self._domain, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Désactive la réécriture DNS."""
        await self.coordinator.async_set_dns_rewrite_status(self._domain, False)