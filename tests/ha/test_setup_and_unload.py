"""Real-HA test for __init__.py: a mocked API loads the entry cleanly, and a mocked
HTTP 400 (the getMyProductInfo schema-drift case from #47's earlier sibling bug) ends in
a clean setup retry rather than an unhandled exception.
"""
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nectr.const import DOMAIN

ENTRY_DATA = {"email": "user@example.com", "password": "secret", "interval": 24}


def _patch_healthy_api():
    return (
        patch("custom_components.nectr.api.NectrApiClient.authenticate", new=AsyncMock(return_value="token")),
        patch(
            "custom_components.nectr.api.NectrApiClient.get_accounts",
            new=AsyncMock(return_value=[{"number": "A-1", "status": "ACTIVE", "state": "QUEENSLAND"}]),
        ),
        patch("custom_components.nectr.api.NectrApiClient.get_usage", new=AsyncMock(return_value={"allUsage": []})),
        patch("custom_components.nectr.api.NectrApiClient.get_account_info", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_power_perks", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_bill_payment_info", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_product_info", new=AsyncMock(return_value={})),
    )


async def test_setup_and_unload_entry(recorder_mock, hass, enable_custom_integrations):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    patches = _patch_healthy_api()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_retries_cleanly_on_schema_drift_400(recorder_mock, hass, enable_custom_integrations):
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    schema_drift_error = ValueError(
        "HTTP 400 from getMyProductInfo: {\"errors\":[{\"message\":\"Cannot query field "
        "\\\"isEligibleForUpdate\\\" on type \\\"MyProduct\\\".\"}]}"
    )

    with patch(
        "custom_components.nectr.api.NectrApiClient.authenticate",
        new=AsyncMock(side_effect=schema_drift_error),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY
