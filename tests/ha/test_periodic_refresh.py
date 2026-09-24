"""Real-HA regression test: the coordinator must refresh again on its own after one interval.

DataUpdateCoordinator only schedules its next refresh while it has listeners. The sensors used
to be plain SensorEntity subclasses, so it had none: the first refresh ran at setup and the
24h timer was never armed, leaving the recorder statistics stale until the next restart or reload.
"""
import logging
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.nectr.const import DOMAIN

ENTRY_DATA = {"email": "user@example.com", "password": "secret", "interval": 24}
API = "custom_components.nectr.api.NectrApiClient"


async def test_coordinator_refreshes_again_after_interval(recorder_mock, hass, enable_custom_integrations, caplog):
    caplog.set_level(logging.INFO, logger="custom_components.nectr")
    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)

    with ExitStack() as stack:
        authenticate = stack.enter_context(patch(f"{API}.authenticate", new=AsyncMock(return_value="token")))
        stack.enter_context(
            patch(f"{API}.get_accounts", new=AsyncMock(return_value=[{"number": "A-1", "state": "QUEENSLAND"}]))
        )
        for method in ("get_usage", "get_account_info", "get_power_perks", "get_bill_payment_info", "get_product_info"):
            stack.enter_context(patch(f"{API}.{method}", new=AsyncMock(return_value={})))

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        after_setup = authenticate.await_count

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=24, minutes=1))
        await hass.async_block_till_done()

        assert authenticate.await_count == after_setup + 1, "coordinator never refreshed after its 24h interval"

    # Loki only sees INFO and above, so these are how a future stall (or a not-yet-published day) shows up.
    assert "Refreshing Nectr data" in caplog.text
    assert "skipping that day" in caplog.text
