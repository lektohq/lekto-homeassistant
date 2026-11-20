"""The actions: upload a file, fetch the mailboxes now."""

from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from homeassistant.components.media_source import Unresolvable
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component
from pylekto import LektoConflictError, LektoConnectionError, LektoValidationError
from pylekto.models import Problem

from custom_components.lekto.const import DOMAIN

from .const import ACCEPTED, MAILBOXES, SPACES, URL, me

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from homeassistant.core import HomeAssistant
    from pytest_homeassistant.common import MockConfigEntry

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
