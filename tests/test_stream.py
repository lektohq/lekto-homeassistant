"""The event stream: events pass on, the numbers follow, the stream comes back."""

import logging
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from pylekto import (
    LektoAuthenticationError,
    LektoConnectionError,
    LektoError,
    LektoForbiddenError,
    LektoRateLimitError,
    LektoTimeoutError,
)
from pylekto.models import Problem

from custom_components.lekto.const import DOMAIN
from custom_components.lekto.coordinator import LektoCoordinator
from custom_components.lekto.stream import RETRY_FIRST, RETRY_LAST, connection_signal, signal

from . import setup_integration
from .const import event, me, streams

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from unittest.mock import MagicMock

    from freezegun.api import FrozenDateTimeFactory
    from homeassistant.core import HomeAssistant
    from pylekto.models import EventMessage
    from pytest_homeassistant.common import MockConfigEntry

pytestmark = pytest.mark.stream


def _logged(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == "custom_components.lekto.stream"
    ]


async def _set_up(hass: HomeAssistant, config_entry: MockConfigEntry) -> list[EventMessage]:
    received: list[EventMessage] = []
    config_entry.add_to_hass(hass)

    @callback
    def take(message: EventMessage) -> None:
        received.append(message)

    async_dispatcher_connect(hass, signal(config_entry), take)
    await setup_integration(hass, config_entry)
    return received


async def test_events(hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry) -> None:
    """Every event passes on; one that changes the numbers fetches them again."""
    lekto.events.listen.side_effect = streams(
        [event("document.node_started", node="ocr", run=1), event("document.received")]
    )

    received = await _set_up(hass, config_entry)

    assert [message.type for message in received] == [
        "document.node_started",
        "document.received",
    ]
    assert lekto.inbox.summary.await_count == 2
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_reconnect(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A lost stream is logged once, connected again with growing waits, and its return logged."""
    lost = LektoConnectionError("refused")
    lekto.events.listen.side_effect = streams(lost, lost, [])

    with (
        caplog.at_level(logging.INFO, "custom_components.lekto.stream"),
        patch("custom_components.lekto.stream.sleep", AsyncMock()) as sleep,
        patch.object(LektoCoordinator, "async_request_refresh", AsyncMock()) as refresh,
    ):
        received = await _set_up(hass, config_entry)

    assert [call.args[0] for call in sleep.await_args_list] == [RETRY_FIRST, RETRY_FIRST * 2]
    assert refresh.await_count == 2
    assert _logged(caplog) == ["Lost the event stream: refused", "The event stream is back"]
    assert received == []
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    "loss",
    [
        [],
        [LektoConnectionError("broken off")],
        LektoRateLimitError(Problem(title="Too Many Requests", status=429), 42.0),
        LektoForbiddenError(Problem(title="Forbidden", status=403)),
    ],
    ids=["ended", "broken off", "rate limited", "forbidden"],
)
async def test_every_loss_logged(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    loss: list[EventMessage | Exception] | Exception,
) -> None:
    """However the stream is lost, the log says so once, and once that it is back."""
    lekto.events.listen.side_effect = streams(loss, [])
    failure = loss[0] if isinstance(loss, list) and loss else loss
    reason = "Lekto ended it" if isinstance(failure, list) else str(failure)

    with (
        caplog.at_level(logging.INFO, "custom_components.lekto.stream"),
        patch("custom_components.lekto.stream.sleep", AsyncMock()),
    ):
        await _set_up(hass, config_entry)

    assert _logged(caplog) == [f"Lost the event stream: {reason}", "The event stream is back"]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


@pytest.mark.parametrize(
    "lost", [LektoConnectionError("refused"), LektoTimeoutError("no answer in time")]
)
async def test_reconnect_waits_at_most(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    lost: LektoError,
) -> None:
    """Each try that fails waits twice as long, however long the try took, up to the longest."""
    failing = streams(*([lost] * 9), [event("document.filed")])

    def listen(**arguments: Any) -> AsyncIterator[EventMessage]:
        # pylekto gives a connection up after ten seconds: longer than the first wait.
        freezer.tick(10)
        return failing(**arguments)

    lekto.events.listen.side_effect = listen

    with patch("custom_components.lekto.stream.sleep", AsyncMock()) as sleep:
        await _set_up(hass, config_entry)

    waits = [call.args[0] for call in sleep.await_args_list]
    assert waits[:3] == [RETRY_FIRST, RETRY_FIRST * 2, RETRY_FIRST * 4]
    assert waits[-2:] == [RETRY_LAST, RETRY_LAST]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_refused(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A token Lekto does not accept ends the stream for good, logged, and asks for a new one."""
    lekto.events.listen.side_effect = streams(
        LektoAuthenticationError(Problem(title="Unauthorized", status=401))
    )

    with caplog.at_level(logging.INFO, "custom_components.lekto.stream"):
        await _set_up(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert lekto.events.listen.call_count == 1
    assert _logged(caplog) == ["Lost the event stream: 401 Unauthorized"]
    state = hass.states.get("event.lekto_document")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


async def test_unexpected_error(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """An error that is none of pylekto's ends the listening; the stream counts as lost then."""
    lekto.connect.return_value = me(rights=["admin:count_all", "documents:count"])
    lekto.events.listen.side_effect = streams([RuntimeError("a bug")])
    await setup_integration(hass, config_entry)
    stream = config_entry.runtime_data.stream
    seen: list[bool] = []

    @callback
    def note() -> None:
        seen.append(stream.connected)

    async_dispatcher_connect(hass, connection_signal(config_entry), note)

    with pytest.raises(RuntimeError, match="a bug"):
        await stream.listen()

    assert seen == [True, False]


async def test_flowing_stream_resets_wait(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """After a stream that flowed, the wait starts short again; a stream that ends flowed too."""
    lost = LektoConnectionError("refused")
    lekto.events.listen.side_effect = streams(lost, lost, [lost], lost, [], [])

    with patch("custom_components.lekto.stream.sleep", AsyncMock()) as sleep:
        await _set_up(hass, config_entry)

    waits = [call.args[0] for call in sleep.await_args_list]
    assert waits == [RETRY_FIRST, RETRY_FIRST * 2, RETRY_FIRST, RETRY_FIRST * 2, RETRY_FIRST]
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_rate_limited(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Lekto's Retry-After stretches the wait."""
    lekto.events.listen.side_effect = streams(
        LektoRateLimitError(Problem(title="Too Many Requests", status=429), 42.0),
        [event("document.filed")],
    )

    with patch("custom_components.lekto.stream.sleep", AsyncMock()) as sleep:
        await _set_up(hass, config_entry)

    assert [call.args[0] for call in sleep.await_args_list] == [42.0]
    assert await hass.config_entries.async_unload(config_entry.entry_id)
