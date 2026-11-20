"""The actions of the Lekto integration: upload a file, fetch the mailboxes now."""

from pathlib import Path
from typing import TYPE_CHECKING

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
from homeassistant.helpers import service
from homeassistant.helpers.os_error import os_read_error
from homeassistant.helpers.selector import MediaSelector
from pylekto import LektoConflictError, LektoError, LektoValidationError

from .capabilities import RIGHTS, Capability
from .const import DOMAIN
from .names import Kind

if TYPE_CHECKING:
    from .coordinator import LektoConfigEntry, LektoCoordinator

CONF_CONFIG_ENTRY_ID = "config_entry_id"
CONF_FILE = "file"
CONF_SPACE = "space"
CONF_MAILBOX = "mailbox"

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
        DOMAIN,
        "fetch_mail",
        _fetch_mail,
        FETCH_MAIL_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


def _coordinator(call: ServiceCall, capability: Capability) -> LektoCoordinator:
    """Every action runs on one entry, and only if its token has the rights."""
    entry: LektoConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[CONF_CONFIG_ENTRY_ID]
    )
    coordinator = entry.runtime_data
    if capability not in coordinator.capabilities:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_lacks_rights",
            translation_placeholders={"rights": ", ".join(sorted(RIGHTS[capability]))},
        )
    return coordinator


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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    return {"document_id": str(accepted.id), "url": _link(coordinator, str(accepted.id))}


async def _space(coordinator: LektoCoordinator, name: str) -> str:
    """Lekto takes a space's id; the user names it."""
    names = coordinator.names
    if not names.may(Kind.SPACE):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="action_lacks_rights",
            translation_placeholders={"rights": ", ".join(sorted(RIGHTS[Capability.SPACES]))},
        )
    try:
        ids = await names.ids(Kind.SPACE, name)
    except LektoError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    if len(ids) != 1:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_name" if not ids else "ambiguous_name",
            translation_placeholders={"name": name},
        )
    return str(ids[0])


async def _fetch_mail(call: ServiceCall) -> ServiceResponse:
    """Lekto fetches by mailbox id; the user names one, or means every active one."""
    coordinator = _coordinator(call, Capability.MAIL)
    wanted = call.data.get(CONF_MAILBOX)
    try:
        mailboxes = await coordinator.client.mailboxes.list()
    except LektoError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="action_failed",
            translation_placeholders={"error": str(err)},
        ) from err
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
