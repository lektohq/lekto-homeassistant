"""Made-up values of the tests, and Lekto's answers read from the fixtures."""

import asyncio
from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from pylekto.models import (
    ClassifierStatusOut,
    DocumentCountOut,
    EventMessage,
    Health,
    InboxSummaryOut,
    JobsSummaryOut,
    Me,
    SearchStatusOut,
)
from pytest_homeassistant.common import load_json_object_fixture

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable

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
    *answers: list[EventMessage] | Exception,
) -> Callable[..., AsyncIterator[EventMessage]]:
    """Return what ``events.listen`` does on each call: events, then stay open; or raise."""
    remaining = list(answers)

    async def listen(**_filters: object) -> AsyncIterator[EventMessage]:
        answer = remaining.pop(0) if remaining else []
        if isinstance(answer, Exception):
            raise answer
        for message in answer:
            yield message
        if not remaining:
            await asyncio.Event().wait()

    return listen
