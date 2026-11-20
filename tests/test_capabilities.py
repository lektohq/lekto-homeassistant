"""The capabilities: what the token's rights allow, and what happens when it loses one."""

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pylekto import LektoConnectionError, LektoForbiddenError
from pylekto.models import Problem
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)

from custom_components.lekto.capabilities import ENTITY_KEYS, Capability
from custom_components.lekto.const import CONF_CAPABILITIES, DOMAIN
from custom_components.lekto.repairs import async_create_fix_flow
from custom_components.lekto.sensor import SENSORS

from .const import ENTRY_DATA, INSTANCE_ID, me, streams

if TYPE_CHECKING:
    from unittest.mock import MagicMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.typing import ClientSessionGenerator

MINIMAL = ["admin:count_all", "documents:count"]
FULL: list[str] = sorted(me().rights)
WITHOUT_SYSTEM = [right for right in FULL if right != "system:read"]
DIAGNOSTIC_SENSORS = [
    "sensor.lekto_jobs_failed",
    "sensor.lekto_jobs_waiting",
    "sensor.lekto_search_index_waiting",
]
FORBIDDEN = LektoForbiddenError(Problem(title="Forbidden", status=403))


def _entry(capabilities: list[str] | None = None) -> MockConfigEntry:
    data = dict(ENTRY_DATA)
    if capabilities is not None:
        data[CONF_CAPABILITIES] = capabilities
    return MockConfigEntry(domain=DOMAIN, title="Lekto", unique_id=INSTANCE_ID, data=data)


async def _set_up(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _next_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    # The coordinator adds a fraction of a second to 60 seconds and refreshes in the background.
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _rights(lekto: MagicMock, rights: list[str]) -> None:
    lekto.connect.return_value = me(rights=rights)
    lekto.auth.me.return_value = me(rights=rights)


async def test_minimal(hass: HomeAssistant, lekto: MagicMock) -> None:
    """With only the household's numbers there are no diagnostics, no events and no stream."""
    _rights(lekto, MINIMAL)
    entry = _entry()

    await _set_up(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.lekto_inbox_open") is not None
    assert hass.states.get("sensor.lekto_health") is not None
    for entity_id in [*DIAGNOSTIC_SENSORS, "event.lekto_document"]:
        assert hass.states.get(entity_id) is None, entity_id
    lekto.jobs.summary.assert_not_called()
    lekto.search.status.assert_not_called()
    lekto.classifier.status.assert_not_called()
    assert entry.data[CONF_CAPABILITIES] == []


@pytest.mark.stream
async def test_minimal_without_stream(hass: HomeAssistant, lekto: MagicMock) -> None:
    """Without the rights of the events the stream is not opened."""
    _rights(lekto, MINIMAL)

    await _set_up(hass, _entry())

    lekto.events.listen.assert_not_called()


async def test_lost_while_running(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A right lost while running sets the entry up again without it, and raises a repair."""
    entry = _entry()
    await _set_up(hass, entry)
    assert entry.data[CONF_CAPABILITIES] == [
        "diagnostics",
        "documents",
        "events",
        "mail",
        "names",
        "spaces",
        "upload",
    ]

    _rights(lekto, WITHOUT_SYSTEM)
    lekto.jobs.summary.side_effect = FORBIDDEN
    await _next_update(hass, freezer)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert lekto.connect.await_count == 2
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_diagnostics_lost")
    assert issue is not None
    assert issue.translation_placeholders == {"name": "Lekto", "rights": "system:read"}
    assert entry.data[CONF_CAPABILITIES] == [
        "diagnostics",
        "documents",
        "events",
        "mail",
        "names",
        "spaces",
        "upload",
    ]


async def test_refused_without_lost_right(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A refused request while Lekto still names the rights does not set the entry up again."""
    entry = _entry()
    await _set_up(hass, entry)

    lekto.jobs.summary.side_effect = FORBIDDEN
    await _next_update(hass, freezer)

    assert lekto.connect.await_count == 1
    state = hass.states.get("sensor.lekto_inbox_open")
    assert state is not None
    assert state.state == "unavailable"


async def test_rights_unknown(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """When Lekto cannot say which rights the token has, nothing is set up again."""
    entry = _entry()
    await _set_up(hass, entry)

    lekto.jobs.summary.side_effect = FORBIDDEN
    lekto.auth.me.side_effect = LektoConnectionError("refused")
    await _next_update(hass, freezer)

    assert lekto.connect.await_count == 1


async def test_required_lost(
    hass: HomeAssistant, lekto: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Losing a right the integration cannot do without asks for a new token."""
    entry = _entry()
    await _set_up(hass, entry)

    _rights(lekto, ["documents:count"])
    lekto.inbox.summary.side_effect = FORBIDDEN
    await _next_update(hass, freezer)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_lost_while_off(hass: HomeAssistant, lekto: MagicMock) -> None:
    """A right lost while Home Assistant was off raises the repair at setup."""
    _rights(lekto, MINIMAL)
    entry = _entry(["diagnostics", "documents", "events", "mail", "names", "spaces", "upload"])

    await _set_up(hass, entry)

    registry = ir.async_get(hass)
    for capability in ("diagnostics", "events"):
        assert registry.async_get_issue(DOMAIN, f"{entry.entry_id}_{capability}_lost")


@pytest.mark.usefixtures("lekto")
async def test_back(hass: HomeAssistant) -> None:
    """A token with the rights again clears the repair."""
    entry = _entry(["diagnostics", "documents", "events", "mail", "names", "spaces", "upload"])
    entry.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry.entry_id}_diagnostics_lost",
        config_entry_id=entry.entry_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="diagnostics_lost",
    )

    await _set_up(hass, entry)

    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_diagnostics_lost") is None


async def _repair(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, lekto: MagicMock
) -> tuple[MockConfigEntry, str]:
    """Set up an entry whose token lost system:read, and open the repair's flow."""
    entry = _entry()
    await _set_up(hass, entry)
    _rights(lekto, WITHOUT_SYSTEM)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, f"{entry.entry_id}_diagnostics_lost")
    assert result["type"] == "menu"
    assert result["menu_options"] == ["new_token", "remove_entities"]
    assert result["description_placeholders"] == {"name": "Lekto", "rights": "system:read"}
    return entry, result["flow_id"]


async def test_repair_remove_entities(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    lekto: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Removing the entities forgets the capability, and the repair does not come back."""
    entry, flow_id = await _repair(hass, hass_client, lekto)
    assert entity_registry.async_get("sensor.lekto_jobs_failed") is not None
    client = await hass_client()

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "remove_entities"})
    assert result["step_id"] == "remove_entities"
    result = await process_repair_fix_flow(client, flow_id, {})

    assert result["type"] == "create_entry"
    for entity_id in DIAGNOSTIC_SENSORS:
        assert entity_registry.async_get(entity_id) is None, entity_id
    assert entity_registry.async_get("sensor.lekto_inbox_open") is not None
    assert entry.data[CONF_CAPABILITIES] == [
        "documents",
        "events",
        "mail",
        "names",
        "spaces",
        "upload",
    ]
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_diagnostics_lost") is None


async def test_repair_new_token(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, lekto: MagicMock
) -> None:
    """Choosing a new token opens the dialog for it."""
    flow_id = (await _repair(hass, hass_client, lekto))[1]
    client = await hass_client()

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "new_token"})

    assert result["type"] == "abort"
    assert result["reason"] == "reauth_started"
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]
    entry_id = hass.config_entries.async_entries(DOMAIN)[0].entry_id
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry_id}_diagnostics_lost")


@pytest.mark.parametrize("data", [None, {"entry_id": "gone", "capability": "diagnostics"}])
async def test_repair_without_entry(
    hass: HomeAssistant, data: dict[str, str | int | float | None] | None
) -> None:
    """A repair whose entry is gone, or that carries nothing, cannot be fixed."""
    with pytest.raises(ValueError, match="entry"):
        await async_create_fix_flow(hass, "issue", data)


@pytest.mark.stream
async def test_stream_refused_after_lost_right(hass: HomeAssistant, lekto: MagicMock) -> None:
    """The stream refused because the token lost the events' rights sets the entry up again."""
    lekto.events.listen.side_effect = streams(FORBIDDEN)
    lekto.connect.side_effect = [me(), me(rights=MINIMAL)]
    lekto.auth.me.return_value = me(rights=MINIMAL)
    entry = _entry()

    await _set_up(hass, entry)
    await hass.async_block_till_done()

    assert lekto.connect.await_count == 2
    assert entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_events_lost")


def test_entity_keys() -> None:
    """The repair removes exactly the entities each capability brings."""
    sensors = {d.key for d in SENSORS if d.capability is Capability.DIAGNOSTICS}
    assert sensors == ENTITY_KEYS[Capability.DIAGNOSTICS]
    assert ENTITY_KEYS[Capability.EVENTS] == {"document"}


async def test_repair_after_rights_came_back(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    lekto: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """A repair left open while a new token brought the rights back removes nothing."""
    entry, flow_id = await _repair(hass, hass_client, lekto)
    client = await hass_client()
    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "remove_entities"})

    _rights(lekto, FULL)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    result = await process_repair_fix_flow(client, flow_id, {})

    assert result["type"] == "abort"
    assert result["reason"] == "issue_gone"
    assert entity_registry.async_get("sensor.lekto_jobs_failed") is not None
    assert entry.data[CONF_CAPABILITIES] == [
        "diagnostics",
        "documents",
        "events",
        "mail",
        "names",
        "spaces",
        "upload",
    ]


async def test_entry_removed(hass: HomeAssistant, lekto: MagicMock) -> None:
    """Removing the entry removes its repairs."""
    _rights(lekto, MINIMAL)
    entry = _entry(["diagnostics"])
    await _set_up(hass, entry)
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, f"{entry.entry_id}_diagnostics_lost")

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert registry.async_get_issue(DOMAIN, f"{entry.entry_id}_diagnostics_lost") is None


async def test_unknown_capability(hass: HomeAssistant, lekto: MagicMock) -> None:
    """A capability of another version is kept, and its repair goes."""
    _rights(lekto, MINIMAL)
    entry = _entry(["mail"])
    entry.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"{entry.entry_id}_mail_lost",
        config_entry_id=entry.entry_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="mail_lost",
    )

    await _set_up(hass, entry)

    assert entry.data[CONF_CAPABILITIES] == ["mail"]
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{entry.entry_id}_mail_lost") is None


async def test_one_reload(hass: HomeAssistant, lekto: MagicMock) -> None:
    """Refused twice at once, the entry is set up again only once."""
    entry = _entry()
    await _set_up(hass, entry)
    coordinator = entry.runtime_data
    _rights(lekto, WITHOUT_SYSTEM)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        await coordinator.reload_if_rights_changed()
        await coordinator.reload_if_rights_changed()

    reload.assert_called_once_with(entry.entry_id)
    assert lekto.auth.me.await_count == 1
