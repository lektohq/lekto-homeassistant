"""The coordinator of the Lekto integration: the household's numbers, every 60 seconds."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pylekto import (
    LektoAuthenticationError,
    LektoError,
    LektoForbiddenError,
    LektoServerError,
)

from .const import DOMAIN, REQUIRED_RIGHTS

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from homeassistant.core import HomeAssistant
    from pylekto import LektoClient
    from pylekto.models import (
        ClassifierStatusOut,
        Health,
        InboxSummaryOut,
        JobsSummaryOut,
        Me,
        SearchStatusOut,
    )

_LOGGER = logging.getLogger(__name__)

type LektoConfigEntry = ConfigEntry[LektoCoordinator]


@dataclass(frozen=True)
class LektoData:
    """The numbers of every user's documents, and the state of Lekto's services and jobs."""

    inbox: InboxSummaryOut
    documents: int
    health: Health
    jobs: JobsSummaryOut
    search: SearchStatusOut | None
    classifier: ClassifierStatusOut | None


class LektoCoordinator(DataUpdateCoordinator[LektoData]):
    """Fetch the numbers of the whole household from one Lekto instance."""

    config_entry: LektoConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: LektoConfigEntry, client: LektoClient, me: Me
    ) -> None:
        """Keep the client and what Lekto said about itself when it connected."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.client = client
        self.instance_id = str(me.instance_id)
        self.lekto_version = me.lekto_version

    @override
    async def _async_update_data(self) -> LektoData:
        """Fetch the inbox's summary, the count of documents and the state of the services."""
        try:
            inbox, count, health, jobs, search, classifier = await asyncio.gather(
                self.client.inbox.summary(all_users=True),
                self.client.documents.count(all_users=True),
                self.client.health.get(),
                self.client.jobs.summary(),
                _unless_missing(self.client.search.status()),
                _unless_missing(self.client.classifier.status()),
            )
        except LektoAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        # A right taken from the token, or an admin who is no admin anymore, refuses a request.
        except LektoForbiddenError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="missing_rights",
                translation_placeholders={"rights": ", ".join(sorted(REQUIRED_RIGHTS))},
            ) from err
        except LektoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return LektoData(
            inbox=inbox,
            documents=count.total,
            health=health,
            jobs=jobs,
            search=search,
            classifier=classifier,
        )


async def _unless_missing[T](request: Awaitable[T]) -> T | None:
    """Lekto runs without a search index or a classifier, and answers 503 for them then."""
    try:
        return await request
    except LektoServerError:
        return None
