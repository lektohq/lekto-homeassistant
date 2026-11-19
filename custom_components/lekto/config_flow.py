"""The config flow of the Lekto integration."""

import logging
from typing import Any, override

import probatio
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from pylekto import (
    LektoAuthenticationError,
    LektoError,
    LektoForbiddenError,
    LektoResponseError,
)

from . import create_client, missing_rights
from .const import DOMAIN, REQUIRED_RIGHTS

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        probatio.Required(probatio.Secret(CONF_API_TOKEN)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
        probatio.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class LektoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Lekto instance with a token made for Home Assistant."""

    VERSION = 1

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the address and the token, and check them against Lekto."""
        errors: dict[str, str] = {}
        placeholders = {
            "rights": ", ".join(sorted(REQUIRED_RIGHTS)),
            "example_url": "https://lekto.example.com",
        }
        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
            client = create_client(self.hass, user_input)
            try:
                me = await client.connect()
            except LektoAuthenticationError:
                errors["base"] = "invalid_auth"
            # An upload token may not even ask who it is.
            except LektoForbiddenError:
                errors["base"] = "missing_rights"
            except LektoResponseError:
                errors["base"] = "unsupported"
            except LektoError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while connecting")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(me.instance_id))
                self._abort_if_unique_id_configured()
                if not missing_rights(me.rights):
                    return self.async_create_entry(title="Lekto", data=user_input)
                errors["base"] = "missing_rights"
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
            description_placeholders=placeholders,
        )
