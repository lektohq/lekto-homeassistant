"""The actions of the Lekto integration: upload, fetch the mailboxes, count and list documents."""

from pathlib import Path
from typing import TYPE_CHECKING, Any

import probatio
from homeassistant.components.media_source import MediaSourceError, async_resolve_media
from homeassistant.const import CONF_NAME, CONF_URL
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.helpers.os_error import os_read_error
from homeassistant.helpers.selector import MediaSelector
from pylekto import LektoConflictError, LektoError, LektoValidationError

from .capabilities import RIGHTS, Capability, rights_text
from .const import DOMAIN
from .names import NEEDS, Kind, document_names

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from homeassistant.util.json import JsonValueType
    from pylekto.models import ListedDocument
    from pylekto.types import ListedFilter

    from .coordinator import LektoConfigEntry, LektoCoordinator

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_FILE = "file"
CONF_SPACE = "space"
CONF_MAILBOX = "mailbox"
CONF_INBOX = "inbox"
CONF_LANE = "lane"
CONF_CONTACT = "contact"
CONF_DOCUMENT_TYPE = "document_type"
CONF_TAG = "tag"
CONF_DATE_FROM = "date_from"
CONF_DATE_TO = "date_to"
CONF_LIMIT = "limit"
CONF_FIELDS = "fields"

LANES = ["green", "yellow", "red", "processing"]
LIST_FIELDS = ["lane", "contact", "document_type", "tags", "space"]

# Only what Lekto processes is offered, so the picker shows no file Lekto would refuse.
ACCEPT = ["application/pdf", "image/jpeg", "image/png", "image/tiff", "message/rfc822"]

UPLOAD_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CONFIG_ENTRY_ID): str,
        probatio.Required(CONF_FILE): MediaSelector({"accept": ACCEPT}),
        probatio.Optional(CONF_NAME): str,
        probatio.Optional(CONF_SPACE): str,
    }
)
FILTERS = {
    probatio.Required(CONF_CONFIG_ENTRY_ID): str,
    probatio.Optional(CONF_INBOX): cv.boolean,
    probatio.Optional(CONF_LANE): probatio.All(cv.ensure_list, [probatio.In(LANES)]),
    probatio.Optional(CONF_CONTACT): probatio.All(cv.ensure_list, [cv.string]),
    probatio.Optional(CONF_DOCUMENT_TYPE): probatio.All(cv.ensure_list, [cv.string]),
    probatio.Optional(CONF_TAG): probatio.All(cv.ensure_list, [cv.string]),
    probatio.Optional(CONF_SPACE): probatio.All(cv.ensure_list, [cv.string]),
    probatio.Optional(CONF_DATE_FROM): cv.date,
    probatio.Optional(CONF_DATE_TO): cv.date,
}
COUNT_SCHEMA = probatio.Schema(FILTERS)
LIST_SCHEMA = probatio.Schema(
    {
        **FILTERS,
        probatio.Optional(CONF_LIMIT, default=10): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=50)
        ),
        probatio.Optional(CONF_FIELDS): probatio.All(cv.ensure_list, [probatio.In(LIST_FIELDS)]),
    }
)
FETCH_MAIL_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_CONFIG_ENTRY_ID): str,
        probatio.Optional(CONF_MAILBOX): str,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions once for the integration; each call names its entry."""
    hass.services.async_register(
        DOMAIN, "upload", _upload, UPLOAD_SCHEMA, supports_response=SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, "count", _count, COUNT_SCHEMA, supports_response=SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN,
        "list_documents",
        _list_documents,
        LIST_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_mail",
        _fetch_mail,
        FETCH_MAIL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _coordinator(call: ServiceCall, capability: Capability | None) -> LektoCoordinator:
    """Every action runs on one entry, and only if its token has the rights."""
    entry: LektoConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
    )
    coordinator = entry.runtime_data
    if capability is not None and capability not in coordinator.capabilities:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_lacks_rights",
            translation_placeholders={"rights": rights_text(RIGHTS[capability])},
        )
    return coordinator


def _failed(err: LektoError) -> HomeAssistantError:
    """Lekto refused or was not reachable: nothing the caller of the action did wrong."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="action_failed",
        translation_placeholders={"error": str(err)},
    )


async def _upload(call: ServiceCall) -> ServiceResponse:
    """Lekto takes bytes; the user picks a file among Home Assistant's media."""
    coordinator = _coordinator(call, Capability.UPLOAD)
    try:
        media = await async_resolve_media(call.hass, call.data[CONF_FILE]["media_content_id"], None)
    except MediaSourceError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_a_local_file",
        ) from err
    if media.path is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_a_local_file")
    space_id = None
    if space := call.data.get(CONF_SPACE):
        space_id = await _space(coordinator, space)
    path = media.path
    try:
        content = await call.hass.async_add_executor_job(path.read_bytes)
    except OSError as err:
        raise os_read_error(err, str(path)) from err
    filename = call.data.get(CONF_NAME) or path.name
    # Lekto tells a mail by its extension, so a given name keeps the file's.
    if not Path(filename).suffix:
        filename += path.suffix
    try:
        accepted = await coordinator.client.documents.upload(content, filename, space_id=space_id)
    except LektoConflictError as err:
        existing = err.existing_document_id
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="already_in_lekto" if existing else "already_in_lekto_unreadable",
            translation_placeholders={"document_id": str(existing)} if existing else None,
        ) from err
    except LektoValidationError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="file_refused",
            translation_placeholders={"error": str(err)},
        ) from err
    except LektoError as err:
        raise _failed(err) from err
    return {"document_id": str(accepted.id), "url": _link(coordinator, str(accepted.id))}


async def _space(coordinator: LektoCoordinator, name: str) -> str:
    """Lekto takes a space's id; the user names it, and it must name one."""
    ids = await _ids(coordinator, Kind.SPACE, name)
    if len(ids) > 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ambiguous_name",
            translation_placeholders={"name": name},
        )
    return str(ids[0])


async def _ids(coordinator: LektoCoordinator, kind: Kind, name: str) -> list[UUID]:
    """Lekto filters by ids, which nobody in Home Assistant knows; the user names them."""
    names = coordinator.names
    if not names.may(kind):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_lacks_rights",
            translation_placeholders={"rights": rights_text(RIGHTS[NEEDS[kind]])},
        )
    try:
        ids = await names.ids(kind, name)
    except LektoError as err:
        raise _failed(err) from err
    if not ids:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_name",
            translation_placeholders={"name": name},
        )
    return ids


async def _filters(coordinator: LektoCoordinator, data: Mapping[str, Any]) -> ListedFilter:
    """Lekto filters by ids within the caller's reach; the household needs `all_users`."""
    filters: ListedFilter = {"all_users": True}
    if (inbox := data.get(CONF_INBOX)) is not None:
        filters["in_inbox"] = inbox
    if lanes := data.get(CONF_LANE):
        filters["lane"] = lanes
    if names := data.get(CONF_CONTACT):
        filters["contact_id"] = await _all_ids(coordinator, Kind.CONTACT, names)
    if names := data.get(CONF_DOCUMENT_TYPE):
        filters["document_type_id"] = await _all_ids(coordinator, Kind.DOCUMENT_TYPE, names)
    if names := data.get(CONF_TAG):
        filters["tag_id"] = await _all_ids(coordinator, Kind.TAG, names)
    if names := data.get(CONF_SPACE):
        filters["space_id"] = await _all_ids(coordinator, Kind.SPACE, names)
    if (start := data.get(CONF_DATE_FROM)) is not None:
        filters["document_date_from"] = start
    if (end := data.get(CONF_DATE_TO)) is not None:
        filters["document_date_to"] = end
    return filters


async def _all_ids(coordinator: LektoCoordinator, kind: Kind, names: list[str]) -> list[UUID]:
    """Several names of one kind take a document that has any of them."""
    return [item_id for name in names for item_id in await _ids(coordinator, kind, name)]


async def _count(call: ServiceCall) -> ServiceResponse:
    """Count with the same filters as the list, so a script can check before it lists."""
    coordinator = _coordinator(call, None)
    filters = await _filters(coordinator, call.data)
    try:
        counted = await coordinator.client.documents.count(**filters)
    except LektoError as err:
        raise _failed(err) from err
    return {"count": counted.total}


async def _list_documents(call: ServiceCall) -> ServiceResponse:
    """List a few of the household's documents, newest first, for a card, a message or a voice."""
    coordinator = _coordinator(call, Capability.DOCUMENTS)
    filters = await _filters(coordinator, call.data)
    wanted = set(call.data.get(CONF_FIELDS, []))
    try:
        page = await coordinator.client.documents.page(
            limit=call.data[CONF_LIMIT], sort="-created_at", **filters
        )
    except LektoError as err:
        raise _failed(err) from err
    documents: list[JsonValueType] = [
        await _listed(coordinator, document, wanted) for document in page.items
    ]
    return {"documents": documents}


async def _listed(
    coordinator: LektoCoordinator, document: ListedDocument, wanted: set[str]
) -> dict[str, JsonValueType]:
    """Give what identifies the document always, the rest when asked: names cost requests."""
    listed: dict[str, JsonValueType] = {
        "id": str(document.id),
        "title": document.title,
        "date": document.document_date.isoformat() if document.document_date else None,
        "url": _link(coordinator, str(document.id)),
    }
    if "lane" in wanted:
        listed["lane"] = document.lane
    single, tags = await document_names(coordinator.names, document, wanted)
    listed |= single
    # Asked for, the tags are there even when the token may not name them: none.
    if "tags" in wanted:
        listed["tags"] = list(tags or [])
    return listed


async def _fetch_mail(call: ServiceCall) -> ServiceResponse:
    """Lekto fetches by mailbox id; the user names one, or means every active one."""
    coordinator = _coordinator(call, Capability.MAIL)
    wanted = call.data.get(CONF_MAILBOX)
    try:
        mailboxes = await coordinator.client.mailboxes.list()
    except LektoError as err:
        raise _failed(err) from err
    chosen = [
        mailbox
        for mailbox in mailboxes
        if (mailbox.name.casefold() == wanted.casefold() if wanted else mailbox.enabled)
    ]
    if wanted and len(chosen) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="ambiguous_name" if chosen else "unknown_name",
            translation_placeholders={"name": wanted},
        )
    for mailbox in chosen:
        try:
            await coordinator.client.mailboxes.fetch(mailbox.id)
        except LektoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="fetch_failed",
                translation_placeholders={"mailbox": mailbox.name, "error": str(err)},
            ) from err
    return {"mailboxes": [mailbox.name for mailbox in chosen]}


def _link(coordinator: LektoCoordinator, document_id: str) -> str:
    """Give an automation a link that opens the document for the user."""
    return f"{coordinator.config_entry.data[CONF_URL]}/ui/documents/{document_id}"
