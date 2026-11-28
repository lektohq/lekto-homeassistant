"""Diagnostics of the Lekto integration: what helps with a problem, without anything personal."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_URL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pydantic import BaseModel

    from .coordinator import LektoConfigEntry

# The unique ID is the instance's id; the title names its host, or what the user called it.
TO_REDACT = {CONF_API_TOKEN, CONF_URL, "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    _hass: HomeAssistant, entry: LektoConfigEntry
) -> dict[str, Any]:
    """Return the entry without token and address, Lekto's versions, the rights and the data."""
    redacted = async_redact_data(entry.as_dict(), TO_REDACT)
    # An entry that failed to set up has no coordinator.
    if entry.state is not ConfigEntryState.LOADED:
        return {"entry": redacted}
    coordinator = entry.runtime_data
    data = coordinator.data
    system = data.diagnostics
    return {
        "entry": redacted,
        "lekto": {
            "lekto_version": coordinator.lekto_version,
            "api_version": coordinator.api_version,
            "rights": coordinator.rights,
            "capabilities": sorted(coordinator.capabilities),
        },
        "data": {
            "inbox": _json(data.inbox),
            "documents": data.documents,
            "health": _json(data.health),
            "jobs": _json(system.jobs if system else None),
            "search": _json(system.search if system else None),
            "classifier": _json(system.classifier if system else None),
            "version": _json(system.version if system else None),
        },
    }


def _json(model: BaseModel | None) -> dict[str, Any] | None:
    """Write nothing for what the token may not read or Lekto runs without."""
    return model.model_dump(mode="json") if model else None
