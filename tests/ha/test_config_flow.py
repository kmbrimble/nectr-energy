"""Real-HA test for the config flow: the user step creates an entry from a mocked auth
call, and a second attempt with the same email is aborted as a duplicate.

Creating an entry auto-triggers HA's real setup of it (coordinator first refresh), so every
NectrApiClient method the coordinator touches needs mocking too, not just authenticate/
get_accounts — otherwise that background setup hits the network and pytest_socket blocks it.
"""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType

from custom_components.nectr.const import DOMAIN

FAKE_ACCOUNTS = [{"number": "A-1", "status": "ACTIVE", "state": "QUEENSLAND"}]


def _patch_full_api(accounts=FAKE_ACCOUNTS):
    return (
        patch("custom_components.nectr.api.NectrApiClient.authenticate", new=AsyncMock(return_value="token")),
        patch("custom_components.nectr.api.NectrApiClient.get_accounts", new=AsyncMock(return_value=accounts)),
        patch("custom_components.nectr.api.NectrApiClient.get_usage", new=AsyncMock(return_value={"allUsage": []})),
        patch("custom_components.nectr.api.NectrApiClient.get_account_info", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_power_perks", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_bill_payment_info", new=AsyncMock(return_value={})),
        patch("custom_components.nectr.api.NectrApiClient.get_product_info", new=AsyncMock(return_value={})),
    )


async def _start_user_step(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})


async def test_user_step_creates_entry(recorder_mock, hass, enable_custom_integrations):
    result = await _start_user_step(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    patches = _patch_full_api()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "user@example.com", "password": "secret"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "sensors"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"]["email"] == "user@example.com"

        await hass.async_block_till_done()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "config_flow.py's async_step_user wraps async_set_unique_id/"
        "_abort_if_unique_id_configured in a bare `except Exception`, which also catches the "
        "AbortFlow control-flow exception those raise — a real duplicate account surfaces as "
        "a generic auth_error form instead of an abort. Reported, not fixed, per this test run's "
        "scope (no changes to config_flow.py)."
    ),
)
async def test_duplicate_email_is_aborted(recorder_mock, hass, enable_custom_integrations):
    patches = _patch_full_api()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        first = await _start_user_step(hass)
        first = await hass.config_entries.flow.async_configure(
            first["flow_id"], {"email": "dupe@example.com", "password": "secret"}
        )
        await hass.config_entries.flow.async_configure(first["flow_id"], {})
        await hass.async_block_till_done()

        second = await _start_user_step(hass)
        second = await hass.config_entries.flow.async_configure(
            second["flow_id"], {"email": "dupe@example.com", "password": "secret"}
        )
        assert second["type"] is FlowResultType.ABORT
        assert second["reason"] == "already_configured"


async def test_no_active_accounts_shows_error(recorder_mock, hass, enable_custom_integrations):
    result = await _start_user_step(hass)
    patches = _patch_full_api(accounts=[])
    with patches[0], patches[1]:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "user2@example.com", "password": "secret"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "no_active_accounts"
