"""Fixtures of the integration's tests: Lekto's answers from files instead of a Lekto."""

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

import pytest
from pylekto.resources.auth import AuthResource
from pylekto.resources.documents import DocumentsResource
from pylekto.resources.events import EventsResource
from pylekto.resources.health import HealthResource
from pylekto.resources.inbox import InboxResource
from pylekto.resources.mail import MailboxesResource
from pylekto.resources.master_data import (
    ContactsResource,
    DocumentTypesResource,
    TagsResource,
)
from pylekto.resources.operations import ClassifierResource, JobsResource
from pylekto.resources.search import SearchResource
from pylekto.resources.spaces import SpacesResource
from pylekto.resources.version import VersionResource
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lekto.const import DOMAIN
from custom_components.lekto.stream import LektoStream

from .const import (
    ACCEPTED,
    CONTACTS,
    DOCUMENT_TYPES,
    ENTRY_DATA,
    INSTANCE_ID,
    MAILBOXES,
    PAGE,
    SPACES,
    TAGS,
    classifier_status,
    document,
    documents_count,
    event,
    health,
    inbox_summary,
    jobs_summary,
    me,
    search_status,
    version,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable, Iterator

    from pylekto.models import EventMessage


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture(autouse=True)
def no_stream(request: pytest.FixtureRequest) -> Iterator[None]:
    """Keep the event stream off, as tests wait for background tasks; ``stream`` marks its own."""
    if request.node.get_closest_marker("stream"):
        yield
        return
    with patch.object(LektoStream, "listen", AsyncMock(return_value=None)):
        yield


async def quiet_stream(
    *, on_connected: Callable[[], None], **_filters: object
) -> AsyncIterator[EventMessage]:
    """Stand for an event stream that flows and stays open without an event."""
    on_connected()
    await asyncio.Event().wait()
    # Never reached; the yield makes this an async generator, as listen() is.
    yield event("document.received")


@pytest.fixture
def lekto_class() -> Iterator[MagicMock]:
    """Replace pylekto's client class with one whose clients answer from the fixtures."""
    with patch("custom_components.lekto.LektoClient", autospec=True) as client_class:
        client = client_class.return_value
        client.connect.return_value = me()
        client.auth = create_autospec(AuthResource, instance=True)
        client.auth.me.return_value = me()
        client.inbox = create_autospec(InboxResource, instance=True)
        client.inbox.summary.return_value = inbox_summary()
        client.documents = create_autospec(DocumentsResource, instance=True)
        client.documents.count.return_value = documents_count()
        client.documents.get.return_value = document()
        client.documents.upload.return_value = ACCEPTED
        client.documents.page.return_value = PAGE
        client.mailboxes = create_autospec(MailboxesResource, instance=True)
        client.mailboxes.list.return_value = MAILBOXES
        client.health = create_autospec(HealthResource, instance=True)
        client.health.get.return_value = health()
        client.jobs = create_autospec(JobsResource, instance=True)
        client.jobs.summary.return_value = jobs_summary()
        client.search = create_autospec(SearchResource, instance=True)
        client.search.status.return_value = search_status()
        client.classifier = create_autospec(ClassifierResource, instance=True)
        client.classifier.status.return_value = classifier_status()
        client.version = create_autospec(VersionResource, instance=True)
        client.version.get.return_value = version()
        client.events = create_autospec(EventsResource, instance=True)
        client.contacts = create_autospec(ContactsResource, instance=True)
        client.contacts.list.return_value = CONTACTS
        client.document_types = create_autospec(DocumentTypesResource, instance=True)
        client.document_types.list.return_value = DOCUMENT_TYPES
        client.tags = create_autospec(TagsResource, instance=True)
        client.tags.list.return_value = TAGS
        client.spaces = create_autospec(SpacesResource, instance=True)
        client.spaces.list.return_value = SPACES
        client.events.listen.side_effect = quiet_stream
        yield client_class


@pytest.fixture
def lekto(lekto_class: MagicMock) -> MagicMock:
    """Return the client the integration makes."""
    client: MagicMock = lekto_class.return_value
    return client


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Keep the config flow's tests from setting the entry up."""
    with patch("custom_components.lekto.async_setup_entry", return_value=None) as setup_entry:
        yield setup_entry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry of the instance in the fixtures."""
    return MockConfigEntry(domain=DOMAIN, title="Lekto", unique_id=INSTANCE_ID, data=ENTRY_DATA)
