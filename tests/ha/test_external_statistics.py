"""Real-HA regression guard for #47: hourly history must land in external statistics
(source `nectr`) via `async_add_external_statistics` with `unit_class` and `mean_type` set,
and the energy sensors must carry no `state_class`. tests/test_external_statistics.py (the
stub version) proved this against hand-written fakes of every homeassistant module; this
proves it against the real recorder, statistics table and entity base classes.
"""
from datetime import datetime, timezone

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import (
    get_last_statistics,
    statistics_during_period,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nectr.coordinator import (
    METRICS,
    NectrDataUpdateCoordinator,
    external_statistic_id,
)
from custom_components.nectr.sensor import NectrEnergySensor


class _FakeApi:
    """Two days of hourly usage, no network."""

    async def get_usage(self, session, account_number, from_date, to_date):
        datetime.strptime(from_date, "%d/%m/%Y")  # raises if the API date format regresses
        return {
            "allUsage": [
                {
                    "period": f"{h}:00",
                    "gridUsage": 0.5,
                    "exportUsage": 0.1 if h == 12 else 0,
                    "controlLoadUsage": None,
                }
                for h in reversed(range(24))
            ]
        }


async def _run_backfill(hass, days=2):
    entry = MockConfigEntry(
        domain="nectr",
        data={"email": "a@b.com", "password": "x", "interval": 24},
    )
    entry.add_to_hass(hass)
    coordinator = NectrDataUpdateCoordinator(hass, entry)
    coordinator.api = _FakeApi()
    await coordinator._backfill_account(None, "A-1", "QUEENSLAND", days)
    await get_instance(hass).async_block_till_done()
    return coordinator


async def test_backfill_writes_valid_external_statistics(recorder_mock, hass, enable_custom_integrations):
    await _run_backfill(hass)

    statistic_id = external_statistic_id("A-1", "grid_consumption")
    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )
    assert statistic_id in last_stats

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    series = await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, start, None, {statistic_id}, "hour", None, {"sum", "state"}
    )
    rows = series[statistic_id]
    assert len(rows) == 48, "two days of hourly data, 24 hours each"
    sums = [row["sum"] for row in rows]
    assert sums == sorted(sums), "sum must be monotonically non-decreasing"
    assert sums[-1] > 0


async def test_backfill_metadata_has_source_unit_class_and_mean_type(recorder_mock, hass, enable_custom_integrations, caplog):
    """The #47 regression itself: pre-#47 metadata (has_mean, no unit_class) still writes
    statistics successfully on HA 2026.9 — `report_usage` only warns, it doesn't yet raise, since
    breaks_in_ha_version=2026.11 hasn't landed. So the only observable signal today is this
    deprecation warning; it's what would have caught #47 before HA 2026.11 turns it into a hard
    failure everywhere.
    """
    await _run_backfill(hass, days=1)

    for metric_key in METRICS:
        statistic_id = external_statistic_id("A-1", metric_key)
        metadata = await get_instance(hass).async_add_executor_job(
            get_last_statistics, hass, 1, statistic_id, True, {"sum"}
        )
        assert statistic_id in metadata

    assert "doesn't specify mean_type" not in caplog.text
    assert "doesn't specify unit_class" not in caplog.text


async def test_energy_sensors_have_no_state_class(recorder_mock, hass, enable_custom_integrations):
    coordinator = await _run_backfill(hass, days=1)
    sensor = NectrEnergySensor(
        coordinator, "A-1", "Grid Consumption", "usage", "gridConsumption", "grid_consumption"
    )
    assert sensor.state_class is None
