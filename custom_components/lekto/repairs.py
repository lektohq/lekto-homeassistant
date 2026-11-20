"""Repairs of the Lekto integration: a capability the token lost."""

from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.components.repairs import RepairsFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .capabilities import ENTITY_KEYS, RIGHTS, Capability
from .const import CONF_CAPABILITIES, DOMAIN

if TYPE_CHECKING:
    from homeassistant.components.repairs import RepairsFlowResult
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant


def _issue_id(entry: ConfigEntry, capability: Capability) -> str:
    return f"{entry.entry_id}_{capability}_lost"


def note_capabilities(
    hass: HomeAssistant, entry: ConfigEntry, given: frozenset[Capability]
) -> None:
    """Raise a repair for each capability the entry had and the token lost, and keep the rest."""
    # An entry from before capabilities were kept knows only what it has now.
    stored: list[str] = entry.data.get(CONF_CAPABILITIES, [str(c) for c in given])
    # A value of another version stays, so that version still knows it after a downgrade.
    kept = sorted({*stored, *given})
    lost = [c for c in Capability if c in stored and c not in given]
    # Issues of this entry not raised again here, such as one of another version, go.
    with ir.async_refresh_issues(hass, DOMAIN, config_entry_id=entry.entry_id):
        for capability in lost:
            ir.async_create_issue(
                hass,
                DOMAIN,
                _issue_id(entry, capability),
                config_entry_id=entry.entry_id,
                is_fixable=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"{capability}_lost",
                translation_placeholders=_placeholders(entry, capability),
                data={"entry_id": entry.entry_id, "capability": str(capability)},
            )
    if entry.data.get(CONF_CAPABILITIES) != kept:
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_CAPABILITIES: kept})


def _placeholders(entry: ConfigEntry, capability: Capability) -> dict[str, str]:
    """Name the entry, as a household may run two instances, and the rights it lacks."""
    return {"name": entry.title, "rights": ", ".join(sorted(RIGHTS[capability]))}


class CapabilityLostRepair(RepairsFlow):
    """Offer a new token, or to remove the entities of the capability the token lost."""

    def __init__(self, entry: ConfigEntry, capability: Capability) -> None:
        """Remember which entry lost which capability."""
        super().__init__()
        self._entry = entry
        self._capability = capability

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> RepairsFlowResult:
        """Let the user choose between a new token and removing the entities."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["new_token", "remove_entities"],
            description_placeholders=_placeholders(self._entry, self._capability),
        )

    async def async_step_new_token(
        self, _user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Ask for a new token; the repair stays until a token with the rights is set up."""
        self._entry.async_start_reauth(self.hass)
        return self.async_abort(reason="reauth_started")

    async def async_step_remove_entities(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Remove the capability's entities and forget it, so the repair does not come back."""
        if user_input is None:
            return self.async_show_form(step_id="remove_entities", data_schema=probatio.Schema({}))
        # A new token may have brought the capability back while the flow was open.
        issue = _issue_id(self._entry, self._capability)
        if ir.async_get(self.hass).async_get_issue(DOMAIN, issue) is None:
            return self.async_abort(reason="issue_gone")
        registry = er.async_get(self.hass)
        wanted = {f"{self._entry.unique_id}_{key}" for key in ENTITY_KEYS[self._capability]}
        for entity in er.async_entries_for_config_entry(registry, self._entry.entry_id):
            if entity.unique_id in wanted:
                registry.async_remove(entity.entity_id)
        kept = [value for value in self._entry.data[CONF_CAPABILITIES] if value != self._capability]
        self.hass.config_entries.async_update_entry(
            self._entry, data={**self._entry.data, CONF_CAPABILITIES: kept}
        )
        return self.async_create_entry(data={})


async def async_create_fix_flow(
    hass: HomeAssistant, _issue_id: str, data: dict[str, str | int | float | None] | None
) -> RepairsFlow:
    """Return the flow that fixes a lost capability."""
    if data is None:
        msg = "A repair of the Lekto integration carries its entry and capability"
        raise ValueError(msg)
    entry = hass.config_entries.async_get_entry(str(data["entry_id"]))
    if entry is None:
        msg = "The entry of the repair is gone"
        raise ValueError(msg)
    return CapabilityLostRepair(entry, Capability(str(data["capability"])))
