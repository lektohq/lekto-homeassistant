"""Fixtures of the integration's tests: Lekto's answers from files instead of a Lekto."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.lekto.const import DOMAIN

from .const import ENTRY_DATA, INSTANCE_ID, me

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def lekto_class() -> Iterator[MagicMock]:
    """Replace pylekto's client class with one whose clients answer from the fixtures."""
    with patch("custom_components.lekto.LektoClient", autospec=True) as client_class:
        client_class.return_value.connect.return_value = me()
        yield client_class


@pytest.fixture
def lekto(lekto_class: MagicMock) -> MagicMock:
    """Return the client the integration makes."""
    client: MagicMock = lekto_class.return_value
    return client


@pytest.fixture
def mock_setup_entry() -> Iterator[AsyncMock]:
    """Keep the config flow's tests from setting the entry up."""
    with patch("custom_components.lekto.async_setup_entry", return_value=None) as setup_entry:
        yield setup_entry


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Return a config entry of the instance in the fixtures."""
    return MockConfigEntry(domain=DOMAIN, title="Lekto", unique_id=INSTANCE_ID, data=ENTRY_DATA)
