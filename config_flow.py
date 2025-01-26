"""Config flow for Glowmarkt integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, APPLICATION_ID
from .glowmarkt_api import GlowmarktAPI

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.debug("Validating user input: %s", data)

    api = GlowmarktAPI(data[CONF_USERNAME], data[CONF_PASSWORD])

    try:
        _LOGGER.debug("Attempting to authenticate with Glowmarkt API")
        await api.authenticate()
    except Exception as err:
        _LOGGER.error("Authentication failed: %s", str(err))
        raise InvalidAuth from err

    _LOGGER.info("Successfully authenticated with Glowmarkt API")
    return {"title": f"Glowmarkt ({data[CONF_USERNAME]})"}

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Glowmarkt."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.debug("Starting async_step_user with input: %s", user_input)

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                _LOGGER.debug("Validating user input")
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                _LOGGER.error("Cannot connect to Glowmarkt API")
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.error("Invalid authentication for Glowmarkt API")
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                _LOGGER.info("Successfully created entry for Glowmarkt integration")
                return self.async_create_entry(title=info["title"], data=user_input)

        _LOGGER.debug("Showing user form")
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

_LOGGER.debug("Config flow module loaded")
