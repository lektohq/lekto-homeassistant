"""The config flow of the Lekto integration."""

import logging
from typing import TYPE_CHECKING, Any, override
from urllib.parse import urlsplit

import probatio
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from pylekto import LektoError

from . import connect_error, create_client
from .capabilities import Capability, missing_rights, rights_text
from .const import CONF_CAPABILITIES, CONF_EVENT_FIELDS, DOMAIN, EVENT_FIELDS, REQUIRED_RIGHTS
from .names import FIELD_KINDS, NEEDS

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .coordinator import LektoConfigEntry

_LOGGER = logging.getLogger(__name__)

_URL = {probatio.Required(CONF_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL))}
_TOKEN = {
    probatio.Required(probatio.Secret(CONF_API_TOKEN)): TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    )
}

USER_SCHEMA = probatio.Schema(
    {**_URL, **_TOKEN, probatio.Required(CONF_VERIFY_SSL, default=True): bool}
)
ADDRESS_SCHEMA = probatio.Schema({**_URL, probatio.Required(CONF_VERIFY_SSL): bool})
TOKEN_SCHEMA = probatio.Schema(_TOKEN)

PLACEHOLDERS = {
    "rights": rights_text(REQUIRED_RIGHTS),
    "example_url": "https://lekto.example.com",
}


class LektoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up one Lekto instance with a token made for Home Assistant."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: LektoConfigEntry) -> LektoOptionsFlow:
        """Return the flow that picks what the document event carries."""
        return LektoOptionsFlow()

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the address and the token, and check them against Lekto."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = _trimmed(user_input[CONF_URL])
            if not (errors := await self._check(user_input)):
                return self.async_create_entry(title=_host(user_input[CONF_URL]), data=user_input)
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
            if not (errors := await self._check({**entry.data, **user_input})):
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders=PLACEHOLDERS,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the address or the TLS check; the token stays, the instance must too."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_URL] = _trimmed(user_input[CONF_URL])
            if not (errors := await self._check({**entry.data, **user_input})):
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ADDRESS_SCHEMA, user_input or entry.data
            ),
            errors=errors,
            description_placeholders={**PLACEHOLDERS, "name": entry.title},
        )

    async def _check(self, data: Mapping[str, Any]) -> dict[str, str]:
        """Connect with ``data`` and return the error to show; none if the token will do.

        The instance comes before the rights: one that is set up already, or another one than
        the entry's, ends the flow whatever its token may do.
        """
        client = create_client(self.hass, data)
        try:
            me = await client.connect()
        except LektoError as err:
            return {"base": connect_error(err)}
        except Exception:
            _LOGGER.exception("Unexpected error while connecting")
            return {"base": "unknown"}
        await self.async_set_unique_id(str(me.instance_id))
        if self.source == SOURCE_USER:
            self._abort_if_unique_id_configured()
        else:
            self._abort_if_unique_id_mismatch()
        return {"base": "missing_rights"} if missing_rights(me.rights) else {}


def _host(url: str) -> str:
    """Name an entry by where its instance lives, so that two instances can be told apart."""
    return urlsplit(url).netloc.rpartition("@")[2]


def _trimmed(url: str) -> str:
    """Return an address as the client takes it: no blanks around it, no slash at its end."""
    return url.strip().rstrip("/")


class LektoOptionsFlow(OptionsFlow):
    """Pick the fields the document event carries beside the document's id."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer the fields the token's rights allow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        entry: LektoConfigEntry = self.config_entry
        # An entry that is not set up goes by the capabilities it last had.
        capabilities = (
            entry.runtime_data.capabilities
            if entry.state is ConfigEntryState.LOADED
            else frozenset(
                Capability(value)
                for value in entry.data.get(CONF_CAPABILITIES, [])
                if value in Capability
            )
        )
        if Capability.EVENTS not in capabilities:
            return self.async_abort(reason="no_events")
        offered = [
            field
            for field in EVENT_FIELDS
            if field not in FIELD_KINDS or NEEDS[FIELD_KINDS[field]] in capabilities
        ]
        schema = probatio.Schema(
            {
                probatio.Optional(CONF_EVENT_FIELDS, default=[]): SelectSelector(
                    SelectSelectorConfig(
                        options=offered, multiple=True, translation_key=CONF_EVENT_FIELDS
                    )
                )
            }
        )
        # A field picked under a token with more rights would be refused by the selector.
        picked = [f for f in entry.options.get(CONF_EVENT_FIELDS, []) if f in offered]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, {CONF_EVENT_FIELDS: picked}),
        )
