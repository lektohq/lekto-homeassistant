"""The names of Lekto's contacts, document types, tags and spaces, kept to filter by them.

Lekto filters by ids, which nobody in Home Assistant knows; the names are fetched once and kept.
"""

import asyncio
import logging
from enum import StrEnum
from time import monotonic
from typing import TYPE_CHECKING, Final, Protocol

from pylekto import LektoError

from .capabilities import Capability

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Sequence
    from uuid import UUID

    from pylekto import LektoClient

_LOGGER = logging.getLogger(__name__)

MAX_AGE: Final = 3600.0
# An unknown name fetches again at once, but not more often, so a typo cannot flood Lekto.
MIN_AGE: Final = 60.0


class Kind(StrEnum):
    """What a name stands for."""

    CONTACT = "contact"
    DOCUMENT_TYPE = "document_type"
    TAG = "tag"
    SPACE = "space"


# The fields of a document that Lekto names by id, and what each stands for.
FIELD_KINDS: Final = {
    "contact": Kind.CONTACT,
    "document_type": Kind.DOCUMENT_TYPE,
    "tags": Kind.TAG,
    "space": Kind.SPACE,
}
NEEDS: Final = {
    Kind.CONTACT: Capability.NAMES,
    Kind.DOCUMENT_TYPE: Capability.NAMES,
    Kind.TAG: Capability.NAMES,
    Kind.SPACE: Capability.SPACES,
}


class _Named(Protocol):
    """pylekto's list models share no base class; this is what the names need of them."""

    @property
    def id(self) -> UUID: ...

    @property
    def name(self) -> str: ...


class LektoNames:
    """The names of one instance, fetched when needed and at most hourly."""

    def __init__(self, client: LektoClient, capabilities: frozenset[Capability]) -> None:
        """Keep the client; only kinds the token may list are fetched."""
        self._client = client
        self._capabilities = capabilities
        self._names: dict[Kind, dict[UUID, str]] = {}
        self._fetched: dict[Kind, float] = {}
        self._failed: dict[Kind, float] = {}
        # Callers at the same time, such as the load at setup and a first event, fetch once.
        self._locks = {kind: asyncio.Lock() for kind in Kind}

    def may(self, kind: Kind) -> bool:
        """Whether the token may list the names of ``kind``."""
        return NEEDS[kind] in self._capabilities

    async def ids(self, kind: Kind, name: str) -> list[UUID]:
        """Return the ids of everything of ``kind`` called ``name``, whatever its case.

        A name not found fetches the names again, unless they were fetched a minute ago.
        """
        found = self._ids(await self._get(kind, MAX_AGE), name)
        if not found:
            found = self._ids(await self._get(kind, MIN_AGE), name)
        return found

    async def name(self, kind: Kind, item_id: UUID) -> str | None:
        """Return the name of ``item_id``, or None if Lekto does not know it (any more)."""
        names = await self._get(kind, MAX_AGE)
        if item_id not in names:
            names = await self._get(kind, MIN_AGE)
        return names.get(item_id)

    async def load(self) -> None:
        """Fetch every kind the token may list, so the first call need not wait."""
        for kind in Kind:
            if not self.may(kind):
                continue
            # Unreachable now, the names are fetched when first needed.
            try:
                await self._get(kind, MAX_AGE)
            except LektoError as err:
                _LOGGER.debug("Could not fetch the names of kind %s: %s", kind, err)

    @staticmethod
    def _ids(names: dict[UUID, str], name: str) -> list[UUID]:
        wanted = name.casefold()
        return [item_id for item_id, known in names.items() if known.casefold() == wanted]

    async def _get(self, kind: Kind, max_age: float) -> dict[UUID, str]:
        async with self._locks[kind]:
            now = monotonic()
            stale = kind not in self._fetched or now - self._fetched[kind] > max_age
            # A refusing Lekto is asked again after a minute, not on every call.
            failed_lately = kind in self._failed and now - self._failed[kind] <= MIN_AGE
            if stale and not failed_lately:
                try:
                    items: Sequence[_Named] = await self._lists()[kind]()
                except LektoError:
                    self._failed[kind] = monotonic()
                    raise
                self._names[kind] = {item.id: item.name for item in items}
                self._fetched[kind] = monotonic()
                self._failed.pop(kind, None)
                _LOGGER.debug("Fetched %d names of kind %s", len(items), kind)
            return self._names.get(kind, {})

    def _lists(self) -> dict[Kind, Callable[[], Awaitable[Sequence[_Named]]]]:
        client = self._client
        return {
            Kind.CONTACT: client.contacts.list,
            Kind.DOCUMENT_TYPE: client.document_types.list,
            Kind.TAG: client.tags.list,
            # Every space of the household, not only the token's user's.
            Kind.SPACE: lambda: client.spaces.list(all_users=True),
        }
