"""The config flow of the Lekto integration."""

import logging
from typing import TYPE_CHECKING, Any, override

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

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pylekto.models import Me

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


TOKEN_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_TOKEN)): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)

PLACEHOLDERS = {
    "rights": ", ".join(sorted(REQUIRED_RIGHTS)),
    "example_url": "https://lekto.example.com",
}


class LektoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Lekto instance with a token made for Home Assistant."""

    VERSION = 1

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the address and the token, and check them against Lekto."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = user_input[CONF_URL].strip().rstrip("/")
            me = await self._connect(user_input)
            if isinstance(me, str):
                errors["base"] = me
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
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reauth(self, _entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Ask for a new token once Lekto refuses the entry's, or it lacks rights."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Check the new token against the same instance and keep it."""
        errors: dict[str, str] = {}
        if user_input is not None:
            entry = self._get_reauth_entry()
            me = await self._connect({**entry.data, **user_input})
            if isinstance(me, str):
                errors["base"] = me
            else:
                await self.async_set_unique_id(str(me.instance_id))
                self._abort_if_unique_id_mismatch()
                if not missing_rights(me.rights):
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
                errors["base"] = "missing_rights"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def _connect(self, data: Mapping[str, Any]) -> Me | str:
        """Shared by the user and reauth steps, so both map pylekto's errors to the same keys."""
        client = create_client(self.hass, data)
        try:
            me = await client.connect()
        except LektoAuthenticationError:
            return "invalid_auth"
        # An upload token may not even ask who it is.
        except LektoForbiddenError:
            return "missing_rights"
        except LektoResponseError:
            return "unsupported"
        except LektoError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error while connecting")
            return "unknown"
        return me
