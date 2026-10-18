"""Config flow to configure the AdGuard Home Extended integration."""

from typing import Any, override
from aiohttp import BasicAuth
from voluptuous import Schema, Required, Optional
from yarl import URL

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER


async def _async_validate_connection(
    hass: HomeAssistant,
    *,
    host: str,
    port: int,
    ssl: bool,
    verify_ssl: bool,
    username: str | None = None,
    password: str | None = None,
) -> str | None:
    """Validate connection to AdGuard Home using direct HTTP requests."""
    scheme = "https" if ssl else "http"
    url = URL.build(scheme=scheme, host=host, port=port).with_path("/control/status")
    
    session = async_get_clientsession(hass, verify_ssl)
    auth = BasicAuth(username, password) if username and password else None

    try:
        async with session.get(url, auth=auth, timeout=10) as response:
            if response.status in (401, 403):
                return "invalid_auth"
            if response.status != 200:
                return "cannot_connect"
    except Exception:
        LOGGER.exception("Unexpected error connecting to AdGuard Home")
        return "unknown"

    return None


class AdGuardExtendedFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an AdGuard Home Extended config flow."""

    DOMAIN = DOMAIN
    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )

            if error := await _async_validate_connection(
                self.hass,
                host=user_input[CONF_HOST],
                port=user_input[CONF_PORT],
                ssl=user_input[CONF_SSL],
                verify_ssl=user_input[CONF_VERIFY_SSL],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            ):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=Schema(
                {
                    Required(CONF_HOST): str,
                    Required(CONF_PORT, default=3000): int,
                    Optional(CONF_USERNAME): str,
                    Optional(CONF_PASSWORD): str,
                    Required(CONF_SSL, default=True): bool,
                    Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )