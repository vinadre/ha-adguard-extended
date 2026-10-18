"""Config flow to configure the AdGuard Home Extended integration."""

from typing import Any, override
from adguardhome import AdGuardHome, AdGuardHomeError
import voluptuous as vol
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

            adguard = AdGuardHome(
                URL.build(
                    scheme="https" if user_input[CONF_SSL] else "http",
                    host=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                ),
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
                verify_ssl=user_input[CONF_VERIFY_SSL],
                session=async_get_clientsession(self.hass, user_input[CONF_VERIFY_SSL]),
            )

            try:
                await adguard.status()
            except AdGuardHomeError as error:
                err_msg = str(error).lower()
                if "auth" in err_msg or "unauthorized" in err_msg or "401" in err_msg or "403" in err_msg:
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                LOGGER.exception("Unexpected error connecting to AdGuard Home")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_HOST],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=3000): int,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(vol.Secret(CONF_PASSWORD)): str,
                    vol.Required(CONF_SSL, default=True): bool,
                    vol.Required(CONF_VERIFY_SSL, default=True): bool,
                }
            ),
            errors=errors,
        )
