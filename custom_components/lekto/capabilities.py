"""What the token lets the integration do, read from the rights Lekto names in GET /auth/me.

Lekto names the rights in effect: ``documents:read`` brings ``documents:count``, and an admin
right counts only while the token's user is an active admin.
"""

from enum import StrEnum
from typing import TYPE_CHECKING, Final

from .const import REQUIRED_RIGHTS

if TYPE_CHECKING:
    from collections.abc import Iterable


class Capability(StrEnum):
    """A function of the integration that the token may lack."""

    DIAGNOSTICS = "diagnostics"
    EVENTS = "events"
    NAMES = "names"
    SPACES = "spaces"
    UPLOAD = "upload"
    MAIL = "mail"
    DOCUMENTS = "documents"


RIGHTS: Final[dict[Capability, frozenset[str]]] = {
    Capability.DIAGNOSTICS: frozenset({"system:read"}),
    Capability.EVENTS: frozenset({"documents:read", "admin:documents_all"}),
    Capability.NAMES: frozenset({"master_data:read"}),
    Capability.SPACES: frozenset({"spaces:read", "admin:documents_all"}),
    Capability.UPLOAD: frozenset({"documents:upload"}),
    Capability.MAIL: frozenset({"system:read", "system:write", "admin:mailboxes"}),
    Capability.DOCUMENTS: frozenset({"documents:read", "admin:documents_all"}),
}

# The repair removes these from the entity registry; a test keeps them in step with the sensors.
# A capability without entities raises no repair: its action names the right it lacks.
ENTITY_KEYS: Final[dict[Capability, frozenset[str]]] = {
    Capability.DIAGNOSTICS: frozenset(
        {
            "jobs_failed",
            "jobs_due",
            "worker_last_started",
            "search_queued",
            "classifier_confirmed_since",
            "update",
        }
    ),
    Capability.EVENTS: frozenset({"document"}),
}


def missing_rights(rights: Iterable[str]) -> list[str]:
    """Return the rights the integration cannot do without that ``rights`` lack, sorted."""
    return sorted(REQUIRED_RIGHTS.difference(rights))


def capabilities(rights: Iterable[str]) -> frozenset[Capability]:
    """Return the capabilities ``rights`` give."""
    given = set(rights)
    return frozenset(capability for capability, needs in RIGHTS.items() if needs <= given)
