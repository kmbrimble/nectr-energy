"""Real-HA regression test: yesterday's usage is retried hourly until Nectr publishes it.

Nectr publishes a day's usage late and at no fixed time. The coordinator only refreshes every 24h
from setup, so a restart that moved that refresh into the early morning (24 Oct 2026: 05:14 AEST)
skipped yesterday and left the Kiosk chart a day short until the next refresh. The hourly retry
has to keep asking until the day lands, then stop costing API calls.
"""
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import get_last_statistics
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.nectr.const import DOMAIN
from custom_components.nectr.coordinator import external_statistic_id

ENTRY_DATA = {"email": "user@example.com", "password": "secret", "interval": 24}
API = "custom_components.nectr.api.NectrApiClient"
BRISBANE = ZoneInfo("Australia/Brisbane")

HOURLY_USAGE = {
    "allUsage": [
        {"period": f"{hour}:00", "gridUsage": 0.5, "exportUsage": 0.1, "controlLoadUsage": 0.2}
        for hour in range(24)
    ]
}


async def _setup_entry(hass, stack, published):
    """Set up the entry with the API faked; `published["yes"]` decides whether Nectr has the day."""
    async def get_usage(*_args, **_kwargs):
        return HOURLY_USAGE if published["yes"] else {}

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    authenticate = stack.enter_context(patch(f"{API}.authenticate", new=AsyncMock(return_value="token")))
    stack.enter_context(
        patch(f"{API}.get_accounts", new=AsyncMock(return_value=[{"number": "A-1", "state": "QUEENSLAND"}]))
    )
    stack.enter_context(patch(f"{API}.get_usage", new=AsyncMock(side_effect=get_usage)))
    for method in ("get_account_info", "get_power_perks", "get_bill_payment_info", "get_product_info"):
        stack.enter_context(patch(f"{API}.{method}", new=AsyncMock(return_value={})))

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return authenticate


async def _fire_top_of_next_hours(hass, hours):
    base = dt_util.utcnow()
    for hour in range(1, hours + 1):
        async_fire_time_changed(hass, base + timedelta(hours=hour, minutes=1))
        await hass.async_block_till_done()
    await get_instance(hass).async_block_till_done()


async def _last_stored_date(hass):
    statistic_id = external_statistic_id("A-1", "grid_consumption")
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    if statistic_id not in last_stats:
        return None
    return dt_util.utc_from_timestamp(last_stats[statistic_id][0]["start"]).astimezone(BRISBANE).date()


async def test_retries_every_hour_while_yesterday_is_unpublished(recorder_mock, hass, enable_custom_integrations):
    published = {"yes": False}
    with ExitStack() as stack:
        authenticate = await _setup_entry(hass, stack, published)
        after_setup = authenticate.await_count

        await _fire_top_of_next_hours(hass, 3)

        assert authenticate.await_count == after_setup + 3, "expected one retry per hour while unpublished"
        assert await _last_stored_date(hass) is None


async def test_imports_yesterday_once_published_then_stops_calling_the_api(recorder_mock, hass, enable_custom_integrations):
    published = {"yes": False}
    yesterday = (dt_util.now(BRISBANE) - timedelta(days=1)).date()
    with ExitStack() as stack:
        authenticate = await _setup_entry(hass, stack, published)
        assert await _last_stored_date(hass) is None

        published["yes"] = True
        await _fire_top_of_next_hours(hass, 1)
        assert await _last_stored_date(hass) == yesterday, "retry did not import yesterday"

        after_import = authenticate.await_count
        await _fire_top_of_next_hours(hass, 3)
        assert authenticate.await_count == after_import, "kept calling the API after yesterday was stored"
