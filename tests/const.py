"""Made-up values of the tests, and Lekto's answers read from the fixtures."""

import asyncio
from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import UUID

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from pylekto.models import (
    ClassifierStatusOut,
    ContactOut,
    DocumentAccepted,
    DocumentCountOut,
    DocumentDetails,
    DocumentPage,
    DocumentTypeOut,
    EventMessage,
    Health,
    InboxSummaryOut,
    JobsSummaryOut,
    ListedDocument,
    MailboxOut,
    Me,
    SearchStatusOut,
    SpaceOut,
    TagOut,
    VersionOut,
)
from pytest_homeassistant.common import load_json_object_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Sequence

INSTANCE_ID = "0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1d00"
DOCUMENT_ID = "0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1e00"
URL = "https://lekto.example.com"
NEW_URL = "https://documents.example.com"
TOKEN = "lekto_madeupTokenForTests"
NEW_TOKEN = "lekto_anotherMadeupToken"
ENTRY_DATA = {CONF_URL: URL, CONF_API_TOKEN: TOKEN, CONF_VERIFY_SSL: True}


def me(**changes: object) -> Me:
    """Return Lekto's answer to ``GET /auth/me`` from the fixture, with ``changes``."""
    return Me.model_validate(load_json_object_fixture("me.json") | changes)


def inbox_summary(**changes: object) -> InboxSummaryOut:
    """Return Lekto's answer to ``GET /inbox/summary`` from the fixture, with ``changes``."""
    return InboxSummaryOut.model_validate(load_json_object_fixture("inbox_summary.json") | changes)


def documents_count() -> DocumentCountOut:
    """Return Lekto's answer to ``GET /documents/count`` from the fixture."""
    return DocumentCountOut.model_validate(load_json_object_fixture("documents_count.json"))


def health(**changes: object) -> Health:
    """Return Lekto's answer to ``GET /health`` from the fixture, with ``changes``."""
    return Health.model_validate(load_json_object_fixture("health.json") | changes)


def jobs_summary(**changes: object) -> JobsSummaryOut:
    """Return Lekto's answer to ``GET /jobs/summary`` from the fixture, with ``changes``."""
    return JobsSummaryOut.model_validate(load_json_object_fixture("jobs_summary.json") | changes)


def search_status() -> SearchStatusOut:
    """Return Lekto's answer to ``GET /search/status`` from the fixture."""
    return SearchStatusOut.model_validate(load_json_object_fixture("search_status.json"))


def version(**changes: object) -> VersionOut:
    """Return Lekto's answer to ``GET /version`` from the fixture, with ``changes``."""
    return VersionOut.model_validate(load_json_object_fixture("version.json") | changes)


def classifier_status() -> ClassifierStatusOut:
    """Return Lekto's answer to ``GET /classifier`` from the fixture."""
    return ClassifierStatusOut.model_validate(load_json_object_fixture("classifier_status.json"))


def event(type_: str, **fields: object) -> EventMessage:
    """Return an event of Lekto's stream with made-up ids."""
    return EventMessage.model_validate(
        {
            "type": type_,
            "id": "0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1e01",
            "occurred_at": "2026-11-19T08:20:00Z",
            "document_id": DOCUMENT_ID,
        }
        | fields
    )


def streams(
    *answers: Sequence[EventMessage | Exception | float] | Exception,
    passes: Callable[[float], object] | None = None,
) -> Callable[..., AsyncIterator[EventMessage]]:
    """Return what ``events.listen`` does on each call.

    An exception stands for a stream that does not start. A list stands for one that flows: its
    events come, a number lets that many seconds pass (by ``passes``, a clock's tick), an
    exception breaks the stream off; the last stream stays open.
    """
    remaining = list(answers)

    async def listen(
        *, on_connected: Callable[[], None], **_filters: object
    ) -> AsyncIterator[EventMessage]:
        answer = remaining.pop(0) if remaining else []
        if isinstance(answer, Exception):
            raise answer
        on_connected()
        for message in answer:
            if isinstance(message, Exception):
                raise message
            if isinstance(message, float):
                assert passes is not None
                passes(message)
                continue
            yield message
        if not remaining:
            await asyncio.Event().wait()

    return listen


# Only the id and the name matter to the integration; the rest of Lekto's answer is left out.
CONTACTS = [
    ContactOut.model_construct(
        id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2001"), name="Example Energy"
    ),
    ContactOut.model_construct(
        id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2002"), name="Sample Insurance"
    ),
    ContactOut.model_construct(
        id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2003"), name="sample insurance"
    ),
]
DOCUMENT_TYPES = [
    DocumentTypeOut.model_construct(id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2101"), name="Invoice")
]
TAGS = [TagOut.model_construct(id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2201"), name="Car")]
SPACES = [
    SpaceOut.model_construct(id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2301"), name="Household")
]


def document(**changes: object) -> DocumentDetails:
    """Return a document as Lekto details it; only the fields the event names are filled."""
    values: dict[str, Any] = {
        "id": UUID(DOCUMENT_ID),
        "title": "Electricity bill November",
        "document_date": date(2026, 11, 3),
        "contact_id": CONTACTS[0].id,
        "document_type_id": DOCUMENT_TYPES[0].id,
        "tag_ids": [TAGS[0].id, UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2fff")],
        "space_id": SPACES[0].id,
    } | changes
    return DocumentDetails.model_construct(**values)


MAILBOXES = [
    MailboxOut.model_construct(
        id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2401"), name="Family", enabled=True
    ),
    MailboxOut.model_construct(
        id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2402"), name="Old", enabled=False
    ),
]
ACCEPTED = DocumentAccepted.model_construct(
    id=UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2501"), status_url="/api/v1/documents/x"
)

LISTED = ListedDocument.model_construct(
    id=UUID(DOCUMENT_ID),
    title="Electricity bill November",
    document_date=date(2026, 11, 3),
    lane="red",
    contact_id=CONTACTS[0].id,
    document_type_id=None,
    tag_ids=[TAGS[0].id],
    space_id=SPACES[0].id,
)
PAGE = DocumentPage.model_construct(
    items=[LISTED, LISTED.model_copy(update={"document_date": None})]
)
