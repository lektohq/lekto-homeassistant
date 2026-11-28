"""Diagnostics of the Lekto integration: what helps with a problem, without anything personal."""

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_URL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

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
    return {
        "entry": redacted,
        "lekto": {
            "lekto_version": coordinator.lekto_version,
            "api_version": coordinator.api_version,
            "rights": coordinator.rights,
            "capabilities": sorted(coordinator.capabilities),
        },
        "data": {
            "inbox": data.inbox.model_dump(mode="json"),
            "documents": data.documents,
            "health": data.health.model_dump(mode="json"),
            "jobs": data.jobs.model_dump(mode="json") if data.jobs else None,
            "search": data.search.model_dump(mode="json") if data.search else None,
            "classifier": data.classifier.model_dump(mode="json") if data.classifier else None,
            "version": data.version.model_dump(mode="json") if data.version else None,
        },
    }
