"""The coordinator of the Lekto integration: the household's numbers, every 60 seconds."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from math import inf
from typing import TYPE_CHECKING, Final, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pylekto import (
    LektoAuthenticationError,
    LektoError,
    LektoForbiddenError,
    LektoRateLimitError,
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

UPDATE_INTERVAL: Final = timedelta(seconds=60)

type LektoConfigEntry = ConfigEntry[LektoCoordinator]


@dataclass(frozen=True)
class LektoDiagnostics:
    """The state of Lekto's jobs and services and its versions: what ``system:read`` opens."""

    jobs: JobsSummaryOut
    search: SearchStatusOut | None
    classifier: ClassifierStatusOut | None
    version: VersionOut


@dataclass(frozen=True)
class LektoData:
    """The numbers of every user's documents, and Lekto's own state where the token may read it."""

    inbox: InboxSummaryOut
    documents: int
    health: Health
    diagnostics: LektoDiagnostics | None

    @property
    def system(self) -> LektoDiagnostics:
        """Return Lekto's own state, for the entities that exist only where the token reads it."""
        if self.diagnostics is None:
            msg = "Lekto's state is fetched only with the right system:read"
            raise RuntimeError(msg)
        return self.diagnostics


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
            update_interval=UPDATE_INTERVAL,
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
            inbox, count, health, diagnostics = await asyncio.gather(
                self.client.inbox.summary(all_users=True),
                self.client.documents.count(all_users=True),
                self.client.health.get(),
                self._diagnostics(),
            )
        except LektoAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="invalid_auth"
            ) from err
        except LektoError as err:
            if isinstance(err, LektoForbiddenError):
                await self.reload_if_rights_changed()
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
                retry_after=self._wait(err),
            ) from err
        # An updated Lekto may speak another API: set up again. So do replicas that take turns.
        before = self.data.diagnostics if self.data else None
        if (
            diagnostics is not None
            and before is not None
            and diagnostics.version.lekto_version != before.version.lekto_version
            and not self._reloading
        ):
            self._reloading = True
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
        return LektoData(inbox=inbox, documents=count.total, health=health, diagnostics=diagnostics)

    def _wait(self, err: LektoError) -> float | None:
        """Take Lekto's wait only where it can neither hasten the fetches nor end them."""
        if not isinstance(err, LektoRateLimitError) or err.retry_after is None:
            return None
        # At setup Home Assistant bounds the wait; later it stands in place of the interval.
        if not self.data or UPDATE_INTERVAL.total_seconds() < err.retry_after < inf:
            return err.retry_after
        return None

    async def _diagnostics(self) -> LektoDiagnostics | None:
        """Fetch the state of the jobs, the services and the versions, if the token may."""
        if Capability.DIAGNOSTICS not in self.capabilities:
            return None
        jobs, search, classifier, version = await asyncio.gather(
            self.client.jobs.summary(),
            _unless_missing(self.client.search.status()),
            _unless_missing(self.client.classifier.status()),
            self.client.version.get(),
        )
        return LektoDiagnostics(jobs=jobs, search=search, classifier=classifier, version=version)


async def _unless_missing[T](request: Awaitable[T]) -> T | None:
    """Lekto runs without a search index or a classifier, and answers 503 for them then."""
    try:
        return await request
    except LektoServerError:
        return None
