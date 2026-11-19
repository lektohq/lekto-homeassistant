"""The coordinator of the Lekto integration: the household's numbers, every 60 seconds."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pylekto import LektoError

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from pylekto import LektoClient
    from pylekto.models import InboxSummaryOut, Me

_LOGGER = logging.getLogger(__name__)

type LektoConfigEntry = ConfigEntry[LektoCoordinator]


@dataclass(frozen=True)
class LektoData:
    """The numbers of every user's documents."""

    inbox: InboxSummaryOut
    documents: int


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
            always_update=False,
        )
        self.client = client
        self.instance_id = str(me.instance_id)
        self.lekto_version = me.lekto_version

    @override
    async def _async_update_data(self) -> LektoData:
        """Fetch the inbox's summary and the count of documents."""
        try:
            inbox, count = await asyncio.gather(
                self.client.inbox.summary(all_users=True),
                self.client.documents.count(all_users=True),
            )
        except LektoError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        return LektoData(inbox=inbox, documents=count.total)
