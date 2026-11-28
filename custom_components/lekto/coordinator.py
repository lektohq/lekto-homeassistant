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
from .stream import LektoStream

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
        VersionOut,
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
    version: VersionOut | None


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
        self.stream = LektoStream(self)
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
        try:
            inbox, count, health, (jobs, search, classifier, version) = await asyncio.gather(
                self.client.inbox.summary(all_users=True),
                self.client.documents.count(all_users=True),
                self.client.health.get(),
                self._diagnostics(),
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
        # A Lekto updated in place may speak another API; setting up again checks it. Only a
        # change between two answers counts, so replicas of two versions cannot reload in a loop.
        before = self.data.version if self.data else None
        if (
            version is not None
            and before is not None
            and version.lekto_version != before.lekto_version
            and not self._reloading
        ):
            self._reloading = True
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        return LektoData(
            inbox=inbox,
            documents=count.total,
            health=health,
            jobs=jobs,
            search=search,
            classifier=classifier,
            version=version,
        )

    async def _diagnostics(
        self,
    ) -> tuple[
        JobsSummaryOut | None, SearchStatusOut | None, ClassifierStatusOut | None, VersionOut | None
    ]:
        """Fetch the state of the jobs, the services and the versions, if the token may."""
        if Capability.DIAGNOSTICS not in self.capabilities:
            return None, None, None, None
        return await asyncio.gather(
            self.client.jobs.summary(),
            _unless_missing(self.client.search.status()),
            _unless_missing(self.client.classifier.status()),
            self.client.version.get(),
        )


async def _unless_missing[T](request: Awaitable[T]) -> T | None:
    """Lekto runs without a search index or a classifier, and answers 503 for them then."""
    try:
        return await request
    except LektoServerError:
        return None
