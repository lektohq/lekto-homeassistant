"""The kept names: ids by name, names by id, fetched when needed."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import UUID

import pytest
from pylekto import LektoConnectionError

from custom_components.lekto.capabilities import Capability
from custom_components.lekto.names import MAX_AGE, MIN_AGE, Kind, LektoNames

from .const import CONTACTS, SPACES, TAGS

if TYPE_CHECKING:
    from collections.abc import Iterator
    from unittest.mock import MagicMock

ALL = frozenset(Capability)


class Clock:
    """A monotonic clock the test moves on."""

    def __init__(self) -> None:
        """Start at a made-up time."""
        self.now = 1000.0

    def __call__(self) -> float:
        """Return the time."""
        return self.now


@pytest.fixture
def clock() -> Iterator[Clock]:
    """Replace the names' clock."""
    clock = Clock()
    with patch("custom_components.lekto.names.monotonic", clock):
        yield clock


async def test_ids_any_case(lekto: MagicMock) -> None:
    """A name finds everything called so, whatever its case."""
    names = LektoNames(lekto, ALL)

    assert await names.ids(Kind.CONTACT, "SAMPLE insurance") == [CONTACTS[1].id, CONTACTS[2].id]
    assert await names.ids(Kind.SPACE, "household") == [SPACES[0].id]
    lekto.spaces.list.assert_awaited_once_with(all_users=True)


async def test_name(lekto: MagicMock) -> None:
    """An id gives its name; an id Lekto does not know gives none."""
    names = LektoNames(lekto, ALL)

    assert await names.name(Kind.CONTACT, CONTACTS[0].id) == "Example Energy"
    assert await names.name(Kind.TAG, UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2fff")) is None


async def test_unknown_name_fetches_again(lekto: MagicMock, clock: Clock) -> None:
    """An unknown name fetches again, but not twice within a minute; known ones not for an hour."""
    names = LektoNames(lekto, ALL)
    assert await names.ids(Kind.CONTACT, "Example Energy")
    assert lekto.contacts.list.await_count == 1

    assert await names.ids(Kind.CONTACT, "Nobody") == []
    assert lekto.contacts.list.await_count == 1

    clock.now += MIN_AGE + 1
    assert await names.ids(Kind.CONTACT, "Nobody") == []
    assert lekto.contacts.list.await_count == 2

    clock.now += MIN_AGE + 1
    assert await names.ids(Kind.CONTACT, "Example Energy")
    assert lekto.contacts.list.await_count == 2

    clock.now += MAX_AGE + 1
    assert await names.ids(Kind.CONTACT, "Example Energy")
    assert lekto.contacts.list.await_count == 3


async def test_unknown_id_fetches_again(lekto: MagicMock, clock: Clock) -> None:
    """An id not among the names fetches again after a minute."""
    names = LektoNames(lekto, ALL)
    other = UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2fff")
    assert await names.name(Kind.CONTACT, other) is None

    clock.now += MIN_AGE + 1
    assert await names.name(Kind.CONTACT, other) is None
    assert lekto.contacts.list.await_count == 2


async def test_load_only_allowed(lekto: MagicMock) -> None:
    """Loading fetches only what the token may list."""
    names = LektoNames(lekto, frozenset({Capability.NAMES}))

    await names.load()

    assert names.may(Kind.CONTACT)
    assert not names.may(Kind.SPACE)
    lekto.contacts.list.assert_awaited_once()
    lekto.document_types.list.assert_awaited_once()
    lekto.tags.list.assert_awaited_once()
    lekto.spaces.list.assert_not_awaited()


async def test_load_unreachable(lekto: MagicMock, clock: Clock) -> None:
    """Loading while Lekto does not answer leaves the names to be fetched a minute later."""
    lekto.contacts.list.side_effect = LektoConnectionError("refused")
    names = LektoNames(lekto, ALL)

    await names.load()

    lekto.contacts.list.side_effect = None
    clock.now += MIN_AGE + 1
    assert await names.ids(Kind.CONTACT, "Example Energy") == [CONTACTS[0].id]


async def test_fetched_once_at_a_time(lekto: MagicMock) -> None:
    """Callers at the same time fetch a kind once."""
    names = LektoNames(lekto, ALL)

    await asyncio.gather(names.load(), names.name(Kind.CONTACT, CONTACTS[0].id))

    lekto.contacts.list.assert_awaited_once()


async def test_failure_asked_again_after_a_minute(lekto: MagicMock, clock: Clock) -> None:
    """A refusing Lekto is asked again after a minute; until then its refusal is the answer."""
    lekto.tags.list.side_effect = LektoConnectionError("refused")
    names = LektoNames(lekto, ALL)
    with pytest.raises(LektoConnectionError):
        await names.ids(Kind.TAG, "Car")

    with pytest.raises(LektoConnectionError, match="refused"):
        await names.ids(Kind.TAG, "Car")
    with pytest.raises(LektoConnectionError, match="refused"):
        await names.name(Kind.TAG, TAGS[0].id)
    assert lekto.tags.list.await_count == 1

    clock.now += MIN_AGE + 1
    lekto.tags.list.side_effect = None
    assert await names.ids(Kind.TAG, "Car")
    assert lekto.tags.list.await_count == 2


async def test_failure_keeps_names_from_before(lekto: MagicMock, clock: Clock) -> None:
    """Names fetched once go on answering while Lekto refuses to give them again."""
    names = LektoNames(lekto, ALL)
    assert await names.ids(Kind.TAG, "Car")
    clock.now += MAX_AGE + 1
    lekto.tags.list.side_effect = LektoConnectionError("refused")
    with pytest.raises(LektoConnectionError):
        await names.ids(Kind.TAG, "Car")

    assert await names.ids(Kind.TAG, "Car") == [TAGS[0].id]
    assert lekto.tags.list.await_count == 2
