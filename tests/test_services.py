"""The actions: upload a file, fetch the mailboxes, count and list documents."""

import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import probatio
import pytest
from homeassistant.components.media_source import Unresolvable
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml import load_yaml_dict
from pylekto import LektoConflictError, LektoConnectionError, LektoValidationError
from pylekto.models import Problem

from custom_components.lekto.const import DOMAIN, EVENT_FIELDS
from custom_components.lekto.services import (
    ACCEPT,
    COUNT_SCHEMA,
    DEFAULT_LIMIT,
    FETCH_MAIL_SCHEMA,
    LANE_FILTERS,
    LIST_FIELDS,
    LIST_SCHEMA,
    MAX_LIMIT,
    UPLOAD_SCHEMA,
)

from .const import (
    ACCEPTED,
    CONTACTS,
    DOCUMENT_ID,
    DOCUMENT_TYPES,
    LISTED,
    MAILBOXES,
    PAGE,
    SPACES,
    TAGS,
    URL,
    me,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "lekto"
SCHEMAS = {
    "upload": UPLOAD_SCHEMA,
    "fetch_mail": FETCH_MAIL_SCHEMA,
    "count": COUNT_SCHEMA,
    "list_documents": LIST_SCHEMA,
}
MEDIA_ID = "media-source://media_source/local/bill.pdf"
FILE = {"media_content_id": MEDIA_ID, "media_content_type": "application/pdf"}


@pytest.fixture
async def loaded(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Return the entry, set up with every right."""
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.runtime_data.client is lekto
    return config_entry


@pytest.fixture
def media(tmp_path: Path) -> Iterator[Path]:
    """Stand for a file in Home Assistant's media, and resolve the media id to it."""
    path = tmp_path / "bill.pdf"
    path.write_bytes(b"%PDF-1.7 made up")
    with patch(
        "custom_components.lekto.services.async_resolve_media",
        return_value=MagicMock(path=path),
    ):
        yield path


async def _call(hass: HomeAssistant, entry: MockConfigEntry, action: str, **data: Any) -> Any:
    return await hass.services.async_call(
        DOMAIN,
        action,
        {"config_entry_id": entry.entry_id, **data},
        blocking=True,
        return_response=True,
    )


@pytest.mark.usefixtures("media")
async def test_upload(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """A file goes to Lekto under its own name; the answer names the document and its link."""
    response = await _call(hass, loaded, "upload", file=FILE)

    lekto.documents.upload.assert_awaited_once_with(b"%PDF-1.7 made up", "bill.pdf", space_id=None)
    assert response == {
        "document_id": str(ACCEPTED.id),
        "url": f"{URL}/ui/documents/{ACCEPTED.id}",
    }


@pytest.mark.usefixtures("media")
async def test_upload_named_into_space(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A given name and a space by its name go along."""
    await _call(
        hass,
        loaded,
        "upload",
        file=FILE,
        name="Electricity.pdf",
        space="HOUSEHOLD",
    )

    lekto.documents.upload.assert_awaited_once_with(
        b"%PDF-1.7 made up", "Electricity.pdf", space_id=str(SPACES[0].id)
    )


@pytest.mark.usefixtures("media")
@pytest.mark.parametrize(
    ("spaces", "key"),
    [
        ([], "unknown_name"),
        ([SPACES[0], SPACES[0].model_copy(update={"id": "x"})], "ambiguous_name"),
    ],
)
async def test_upload_space_not_one(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry, spaces: list[Any], key: str
) -> None:
    """A space name that matches none, or more than one, is refused."""
    lekto.spaces.list.return_value = spaces
    loaded.runtime_data.names._fetched.clear()

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "upload", file=FILE, space="Household")

    assert raised.value.translation_key == key


@pytest.mark.usefixtures("media")
async def test_upload_already_in_lekto(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A file Lekto holds already names the document it holds."""
    existing = UUID("0195f3c2-7a10-7c4e-9b1d-2f6a8e4c2599")
    lekto.documents.upload.side_effect = LektoConflictError(
        Problem(title="Conflict", status=409, existing_document_id=existing)
    )

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "already_in_lekto"
    assert raised.value.translation_placeholders == {"document_id": str(existing)}


@pytest.mark.usefixtures("media")
async def test_upload_failed(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """Lekto not answering fails the action."""
    lekto.documents.upload.side_effect = LektoConnectionError("refused")

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "action_failed"


async def test_upload_not_local(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """Media that is no file in Home Assistant cannot go to Lekto."""
    with (
        patch(
            "custom_components.lekto.services.async_resolve_media",
            return_value=MagicMock(path=None),
        ),
        pytest.raises(ServiceValidationError) as raised,
    ):
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "not_a_local_file"


async def test_upload_unreadable(hass: HomeAssistant, loaded: MockConfigEntry, media: Path) -> None:
    """A file that cannot be read fails the action."""
    await hass.async_add_executor_job(media.unlink)

    with pytest.raises(HomeAssistantError):
        await _call(hass, loaded, "upload", file=FILE)


@pytest.mark.usefixtures("media")
async def test_upload_space_without_rights(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A space by name needs the right to list the spaces."""
    lekto.connect.return_value = me(rights=[r for r in me().rights if r != "spaces:read"])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, config_entry, "upload", file=FILE, space="Household")

    assert raised.value.translation_key == "action_lacks_rights"


@pytest.mark.usefixtures("media")
async def test_upload_space_unreachable(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """Lekto not giving the spaces fails the action."""
    loaded.runtime_data.names._fetched.clear()
    lekto.spaces.list.side_effect = LektoConnectionError("refused")

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, loaded, "upload", file=FILE, space="Household")

    assert raised.value.translation_key == "action_failed"


@pytest.mark.parametrize(
    "case",
    [
        ("upload", "documents:upload", {"file": FILE}),
        ("fetch_mail", "admin:mailboxes", {}),
    ],
)
async def test_lacks_rights(
    hass: HomeAssistant,
    lekto: MagicMock,
    config_entry: MockConfigEntry,
    case: tuple[str, str, dict[str, Any]],
) -> None:
    """An action whose rights the token lacks names them."""
    action, right, data = case
    lekto.connect.return_value = me(rights=[r for r in me().rights if r != right])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, config_entry, action, **data)

    assert raised.value.translation_key == "action_lacks_rights"
    assert raised.value.translation_placeholders is not None
    assert right in raised.value.translation_placeholders["rights"].split(", ")


async def test_fetch_mail(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """Without a name every active mailbox is fetched."""
    response = await _call(hass, loaded, "fetch_mail")

    lekto.mailboxes.fetch.assert_awaited_once_with(MAILBOXES[0].id)
    assert response == {"mailboxes": ["Family"]}


async def test_fetch_one_mailbox(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A named mailbox is fetched, active or not."""
    response = await _call(hass, loaded, "fetch_mail", mailbox="old")

    lekto.mailboxes.fetch.assert_awaited_once_with(MAILBOXES[1].id)
    assert response == {"mailboxes": ["Old"]}


async def test_fetch_unknown_mailbox(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """A name no mailbox has is refused."""
    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "fetch_mail", mailbox="Nobody")

    assert raised.value.translation_key == "unknown_name"


@pytest.mark.parametrize(("failing", "key"), [("list", "action_failed"), ("fetch", "fetch_failed")])
async def test_fetch_failed(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry, failing: str, key: str
) -> None:
    """Lekto not answering fails the action, naming the mailbox it stopped at."""
    getattr(lekto.mailboxes, failing).side_effect = LektoConnectionError("refused")

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, loaded, "fetch_mail")

    assert raised.value.translation_key == key


async def test_entry_not_loaded(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """An action on an entry that is not set up is refused."""
    assert await async_setup_component(hass, DOMAIN, {})
    config_entry.add_to_hass(hass)

    with pytest.raises(ServiceValidationError):
        await _call(hass, config_entry, "fetch_mail")


@pytest.mark.usefixtures("media")
async def test_upload_already_in_unreadable(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A file Lekto holds in a document the token may not read is refused without an id."""
    lekto.documents.upload.side_effect = LektoConflictError(Problem(title="Conflict", status=409))

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "already_in_lekto_unreadable"


@pytest.mark.usefixtures("media")
async def test_upload_refused(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A file Lekto refuses is the user's to change."""
    lekto.documents.upload.side_effect = LektoValidationError(
        Problem(title="Unprocessable", status=422)
    )

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "file_refused"


async def test_upload_unresolvable(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """Media Home Assistant cannot resolve is refused."""
    with (
        patch(
            "custom_components.lekto.services.async_resolve_media",
            side_effect=Unresolvable("Unknown source"),
        ),
        pytest.raises(ServiceValidationError) as raised,
    ):
        await _call(hass, loaded, "upload", file=FILE)

    assert raised.value.translation_key == "not_a_local_file"


@pytest.mark.usefixtures("media")
async def test_upload_name_keeps_extension(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A given name without an extension keeps the file's."""
    await _call(hass, loaded, "upload", file=FILE, name="Electricity")

    lekto.documents.upload.assert_awaited_once_with(
        b"%PDF-1.7 made up", "Electricity.pdf", space_id=None
    )


@pytest.mark.usefixtures("media")
async def test_upload_without_response(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """The action runs without asking for its response, too."""
    await hass.services.async_call(
        DOMAIN, "upload", {"config_entry_id": loaded.entry_id, "file": FILE}, blocking=True
    )

    lekto.documents.upload.assert_awaited_once()


async def test_fetch_ambiguous_mailbox(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A name two mailboxes share is refused."""
    lekto.mailboxes.list.return_value = [MAILBOXES[0], MAILBOXES[0]]

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "fetch_mail", mailbox="Family")

    assert raised.value.translation_key == "ambiguous_name"
    lekto.mailboxes.fetch.assert_not_awaited()


async def test_count_all(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """Without filters every document of the household counts."""
    response = await _call(hass, loaded, "count")

    lekto.documents.count.assert_awaited_with(all_users=True)
    assert response == {"count": 1234}


async def test_count_filtered(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """Names become ids; a name several share takes all of them."""
    await _call(
        hass,
        loaded,
        "count",
        inbox=True,
        lane=["red", "processing"],
        contact=["sample insurance"],
        document_type="Invoice",
        tag=["Car"],
        space=["Household"],
        date_from="2026-01-01",
        date_to="2026-11-30",
    )

    lekto.documents.count.assert_awaited_with(
        all_users=True,
        in_inbox=True,
        lane=["red", "processing"],
        contact_id=[CONTACTS[1].id, CONTACTS[2].id],
        document_type_id=[DOCUMENT_TYPES[0].id],
        tag_id=[TAGS[0].id],
        space_id=[SPACES[0].id],
        document_date_from=date(2026, 1, 1),
        document_date_to=date(2026, 11, 30),
    )


async def test_outside_the_inbox(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """Off takes the documents not in the inbox, as Lekto's own false does."""
    await _call(hass, loaded, "list_documents", inbox=False)

    lekto.documents.page.assert_awaited_once_with(
        limit=10, sort="-created_at", all_users=True, in_inbox=False
    )


async def test_count_unknown_name(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """A name Lekto does not know is refused."""
    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, loaded, "count", contact=["Nobody"])

    assert raised.value.translation_key == "unknown_name"


async def test_count_name_without_rights(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """A filter by name needs the right to list the names."""
    lekto.connect.return_value = me(rights=[r for r in me().rights if r != "master_data:read"])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, config_entry, "count", tag=["Car"])

    assert raised.value.translation_key == "action_lacks_rights"


async def test_count_names_never_fetched(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """While Lekto has given no names yet, a filter by name fails as Lekto does, not as unknown."""
    lekto.contacts.list.side_effect = LektoConnectionError("refused")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, config_entry, "count", contact=["Example Energy"])

    assert raised.value.translation_key == "action_failed"
    assert lekto.contacts.list.await_count == 1


async def test_count_failed(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """Lekto not answering fails the action."""
    lekto.documents.count.side_effect = LektoConnectionError("refused")

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, loaded, "count")

    assert raised.value.translation_key == "action_failed"


async def test_list(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """The newest ten of the household, each with id, title, date and link."""
    response = await _call(hass, loaded, "list_documents")

    lekto.documents.page.assert_awaited_once_with(limit=10, sort="-created_at", all_users=True)
    link = f"{URL}/ui/documents/{DOCUMENT_ID}"
    assert response == {
        "documents": [
            {
                "id": DOCUMENT_ID,
                "title": "Electricity bill November",
                "date": "2026-11-03",
                "url": link,
            },
            {"id": DOCUMENT_ID, "title": "Electricity bill November", "date": None, "url": link},
        ]
    }


async def test_list_fields(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """Asked fields come with their names; one Lekto cannot name stays empty."""
    response = await _call(
        hass,
        loaded,
        "list_documents",
        limit=1,
        fields=["lane", "contact", "document_type", "tags", "space"],
    )

    lekto.documents.page.assert_awaited_once_with(limit=1, sort="-created_at", all_users=True)
    first = response["documents"][0]
    assert {key: first[key] for key in ("lane", "contact", "document_type", "tags", "space")} == {
        "lane": "red",
        "contact": "Example Energy",
        "document_type": None,
        "tags": ["Car"],
        "space": "Household",
    }


async def test_list_fields_without_names(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """Without the rights to list names, the named fields stay empty."""
    rights = [r for r in me().rights if r not in {"master_data:read", "spaces:read"}]
    lekto.connect.return_value = me(rights=rights)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    response = await _call(hass, config_entry, "list_documents", fields=["contact", "tags"])

    assert response["documents"][0]["contact"] is None
    assert response["documents"][0]["tags"] == []


async def test_list_failed(hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry) -> None:
    """Lekto not answering fails the action."""
    lekto.documents.page.side_effect = LektoConnectionError("refused")

    with pytest.raises(HomeAssistantError) as raised:
        await _call(hass, loaded, "list_documents")

    assert raised.value.translation_key == "action_failed"


async def test_list_without_rights(
    hass: HomeAssistant, lekto: MagicMock, config_entry: MockConfigEntry
) -> None:
    """The list needs the rights to read the household's documents."""
    lekto.connect.return_value = me(rights=["admin:count_all", "documents:count"])
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as raised:
        await _call(hass, config_entry, "list_documents")

    assert raised.value.translation_key == "action_lacks_rights"


async def test_list_limit(hass: HomeAssistant, loaded: MockConfigEntry) -> None:
    """More than 50 is refused."""
    with pytest.raises(probatio.Invalid):
        await _call(hass, loaded, "list_documents", limit=51)


async def test_single_values(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A single lane or field may come without a list, as YAML writes it."""
    response = await _call(
        hass, loaded, "list_documents", lane="red", contact="Example Energy", fields="lane"
    )

    lekto.documents.page.assert_awaited_once_with(
        limit=10,
        sort="-created_at",
        all_users=True,
        lane=["red"],
        contact_id=[CONTACTS[0].id],
    )
    assert response["documents"][0]["lane"] == "red"


@pytest.mark.parametrize("data", [{"lane": ["purple"]}, {"fields": ["title"]}])
async def test_refused_values(
    hass: HomeAssistant, loaded: MockConfigEntry, data: dict[str, Any]
) -> None:
    """A lane or field the action does not know is refused."""
    with pytest.raises(probatio.Invalid):
        await _call(hass, loaded, "list_documents", **data)


async def test_list_processing_and_unnamed(
    hass: HomeAssistant, lekto: MagicMock, loaded: MockConfigEntry
) -> None:
    """A document in processing has no lane; a name Lekto cannot give now is empty."""
    lekto.documents.page.return_value = PAGE.model_copy(
        update={"items": [LISTED.model_copy(update={"lane": None})]}
    )
    loaded.runtime_data.names._fetched.clear()
    lekto.contacts.list.side_effect = LektoConnectionError("refused")

    response = await _call(hass, loaded, "list_documents", fields=["lane", "contact"])

    assert response["documents"][0]["lane"] is None
    assert response["documents"][0]["contact"] is None


def test_services_yaml_in_step() -> None:
    """The action editor offers what the schemas take: fields, lanes, file types, the limit."""
    described = load_yaml_dict(str(INTEGRATION / "services.yaml"))

    assert {
        action: {name: field["required"] for name, field in described[action]["fields"].items()}
        for action in described
    } == {
        action: {key.schema: isinstance(key, probatio.Required) for key in schema.schema}
        for action, schema in SCHEMAS.items()
    }
    listed = described["list_documents"]["fields"]
    assert described["upload"]["fields"]["file"]["selector"]["media"]["accept"] == ACCEPT
    assert listed["lane"]["selector"]["select"]["options"] == LANE_FILTERS
    assert listed["fields"]["selector"]["select"]["options"] == LIST_FIELDS
    assert listed["limit"]["default"] == DEFAULT_LIMIT
    assert listed["limit"]["selector"]["number"] == {"min": 1, "max": MAX_LIMIT, "mode": "box"}


@pytest.mark.parametrize("language", ["en", "de"])
def test_selectors_translated(language: str) -> None:
    """Every choice a selector offers has its text, and no text stands for a choice long gone."""
    path = INTEGRATION / "translations" / f"{language}.json"
    selectors = json.loads(path.read_text(encoding="utf-8"))["selector"]

    assert {name: list(selector["options"]) for name, selector in selectors.items()} == {
        "document_fields": LIST_FIELDS,
        "event_fields": list(EVENT_FIELDS),
        "lane": LANE_FILTERS,
    }
