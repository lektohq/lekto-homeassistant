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

from .capabilities import Capability, capabilities, missing_rights
from .const import DOMAIN
from .names import LektoNames

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

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
    jobs: JobsSummaryOut | None
    search: SearchStatusOut | None
    classifier: ClassifierStatusOut | None


class LektoCoordinator(DataUpdateCoordinator[LektoData]):
    """Fetch the numbers of the whole household from one Lekto instance."""

    config_entry: LektoConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LektoConfigEntry,
        client: LektoClient,
        me: Me,
        given: frozenset[Capability],
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
        self.api_version = me.api_version
        self.rights = sorted(me.rights)
        self.capabilities = given
        self.names = LektoNames(client, given)
        self._reloading = False

    async def reload_if_rights_changed(self) -> None:
        """Set the entry up again when Lekto names other rights than at setup.

        A refused request alone does not tell; reloading on it could loop.
        """
        # The stream and the numbers may both be refused at once; one reload is enough.
        if self._reloading:
            return
        try:
            me = await self.client.auth.me()
        except LektoError:
            return
        if missing_rights(me.rights) or capabilities(me.rights) != self.capabilities:
            self._reloading = True
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    @override
    async def _async_update_data(self) -> LektoData:
        """Fetch the inbox's summary, the count of documents and the state of the services."""
        diagnostics = Capability.DIAGNOSTICS in self.capabilities
        try:
            inbox, count, health, jobs, search, classifier = await asyncio.gather(
                self.client.inbox.summary(all_users=True),
                self.client.documents.count(all_users=True),
                self.client.health.get(),
                _if(self.client.jobs.summary, wanted=diagnostics),
                _if(lambda: _unless_missing(self.client.search.status()), wanted=diagnostics),
                _if(lambda: _unless_missing(self.client.classifier.status()), wanted=diagnostics),
            )
        except LektoAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except LektoForbiddenError as err:
            await self.reload_if_rights_changed()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
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


async def _if[T](request: Callable[[], Awaitable[T]], *, wanted: bool) -> T | None:
    """Without the right a request would only be refused, so it is not sent."""
    return await request() if wanted else None
