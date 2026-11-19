"""Made-up values of the tests, and Lekto's answers read from the fixtures."""

from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from pylekto.models import DocumentCountOut, InboxSummaryOut, Me
from pytest_homeassistant.common import load_json_object_fixture

INSTANCE_ID = "0195f3c2-7a10-7c4e-9b1d-2f6a8e4c1d00"
URL = "https://lekto.example.com"
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
