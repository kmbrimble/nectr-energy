"""Real-HA regression tests: a day Nectr publishes late is filled even after later days are stored.

On 6 Nov 2026 Nectr returned nothing for Friday until well after it had published Saturday. The
coordinator only looks forward from the last stored day, so once 7 Nov was stored 6 Nov was never
asked for again and the Kiosk chart kept an empty slot until a manual `nectr.backfill_history`.
Statistics hold a cumulative `sum`, so filling the day also has to move every later row's sum.
"""
from contextlib import ExitStack
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    statistics_during_period,
)
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nectr.const import DOMAIN
from custom_components.nectr.coordinator import (
    METRICS,
    _interior_gaps,
    _statistic_metadata,
    external_statistic_id,
)

ENTRY_DATA = {"email": "user@example.com", "password": "secret", "interval": 24}
API = "custom_components.nectr.api.NectrApiClient"
BRISBANE = ZoneInfo("Australia/Brisbane")
ACCOUNT = "A-1"

# Each day's hourly usage differs, so a mis-ordered or mis-based sum cannot hide behind equal values.
def _day_usage(day):
    grid = 0.1 * (day.day % 7 + 1)
    return {"allUsage": [
        {"period": f"{hour}:00", "gridUsage": grid, "exportUsage": 0.01, "controlLoadUsage": 0.0}
        for hour in range(24)
    ]}


def _local_midnight(day):
    return datetime.combine(day, datetime.min.time(), tzinfo=BRISBANE)


def _seed(hass, days):
    """Store `days` as a cumulative series the way the integration does (one row per hour)."""
    for metric_key, usage_key in METRICS.items():
        running = 0.0
        rows = []
        for day in days:
            for item in _day_usage(day)["allUsage"]:
                value = float(item[usage_key])
                running += value
                rows.append(StatisticData(
                    start=_local_midnight(day).replace(hour=int(item["period"].split(":")[0])),
                    state=value,
                    sum=running,
                ))
        async_add_external_statistics(hass, _statistic_metadata(ACCOUNT, metric_key), rows)


async def _stored_rows(hass, metric_key="grid_consumption"):
    await get_instance(hass).async_block_till_done()
    statistic_id = external_statistic_id(ACCOUNT, metric_key)
    result = await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, _local_midnight(dt_util.now(BRISBANE).date() - timedelta(days=60)),
        None, {statistic_id}, "hour", None, {"state", "sum"},
    )
    return result.get(statistic_id, [])


def _stored_days(rows):
    return {dt_util.utc_from_timestamp(row["start"]).astimezone(BRISBANE).date() for row in rows}


async def _setup_entry(hass, stack, published_days):
    """Set up the entry with the API faked; `published_days` is the set of days Nectr has."""
    async def get_usage(_session, _account, from_date=None, _to_date=None):
        if from_date is None:
            return {}  # the refresh's own no-date-range call; only the dated history calls matter here
        day = datetime.strptime(from_date, "%d/%m/%Y").date()
        return _day_usage(day) if day in published_days else {}

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    authenticate = stack.enter_context(patch(f"{API}.authenticate", new=AsyncMock(return_value="token")))
    stack.enter_context(
        patch(f"{API}.get_accounts", new=AsyncMock(return_value=[{"number": ACCOUNT, "state": "QUEENSLAND"}]))
    )
    stack.enter_context(patch(f"{API}.get_usage", new=AsyncMock(side_effect=get_usage)))
    for method in ("get_account_info", "get_power_perks", "get_bill_payment_info", "get_product_info"):
        stack.enter_context(patch(f"{API}.{method}", new=AsyncMock(return_value={})))

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await get_instance(hass).async_block_till_done()
    return entry, hass.data[DOMAIN][entry.entry_id], authenticate


async def _unload(hass, entry):
    """Cancel the hourly listener so nothing fires while the fixtures tear down."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def _retry_at_local_hour(hass, coordinator, hour):
    """Call the hourly retry as the listener would, without faking the clock.

    Firing fake time against the real clock loses ticks and lets timers fire during teardown when
    the runner is busy (see tests/ha/test_hourly_history_retry.py), so the hour is passed in.
    """
    now = dt_util.now().replace(hour=hour, minute=0, second=0, microsecond=0)
    await coordinator._async_retry_missing_history(now)
    await hass.async_block_till_done()
    await get_instance(hass).async_block_till_done()


def _assert_cumulative(rows):
    """Each row's sum is the previous sum plus its own state: no gap-sized jump anywhere."""
    running = 0.0
    for row in rows:
        running += row["state"]
        assert abs(row["sum"] - running) < 1e-6, f"sum jumps at {row['start']}: {row['sum']} != {running}"


def test_interior_gaps_ignores_leading_and_trailing_days():
    def rows(*days):
        return [{"start": _local_midnight(day).timestamp()} for day in days]

    d = lambda n: datetime(2026, 11, 1).date() + timedelta(days=n)
    assert _interior_gaps([], BRISBANE) == []
    assert _interior_gaps(rows(d(0)), BRISBANE) == []
    assert _interior_gaps(rows(d(0), d(1), d(2)), BRISBANE) == []
    assert _interior_gaps(rows(d(0), d(3)), BRISBANE) == [d(1), d(2)]
    assert _interior_gaps(rows(d(0), d(1), d(4), d(6)), BRISBANE) == [d(2), d(3), d(5)]


async def test_fills_a_skipped_day_and_rebases_later_sums(recorder_mock, hass, enable_custom_integrations):
    yesterday = dt_util.now(BRISBANE).date() - timedelta(days=1)
    days = [yesterday - timedelta(days=n) for n in range(5, -1, -1)]
    skipped = days[2]
    _seed(hass, [day for day in days if day != skipped])
    await get_instance(hass).async_block_till_done()
    assert skipped not in _stored_days(await _stored_rows(hass))

    with ExitStack() as stack:
        entry, _coordinator, _authenticate = await _setup_entry(hass, stack, published_days=set(days))
    await _unload(hass, entry)

    for metric_key in METRICS:
        rows = await _stored_rows(hass, metric_key)
        assert _stored_days(rows) == set(days), f"{metric_key}: skipped day was not filled"
        assert len(rows) == 24 * len(days), f"{metric_key}: duplicate or missing hours"
        _assert_cumulative(rows)

    grid = await _stored_rows(hass, "grid_consumption")
    expected_total = sum(item["gridUsage"] for day in days for item in _day_usage(day)["allUsage"])
    assert abs(grid[-1]["sum"] - expected_total) < 1e-6


async def test_a_day_nectr_still_lacks_stays_empty_and_changes_nothing(recorder_mock, hass, enable_custom_integrations):
    yesterday = dt_util.now(BRISBANE).date() - timedelta(days=1)
    days = [yesterday - timedelta(days=n) for n in range(4, -1, -1)]
    skipped = days[2]
    _seed(hass, [day for day in days if day != skipped])
    before = await _stored_rows(hass)

    with ExitStack() as stack:
        entry, _coordinator, _authenticate = await _setup_entry(hass, stack, published_days=set(days) - {skipped})
    await _unload(hass, entry)

    after = await _stored_rows(hass)
    assert _stored_days(after) == set(days) - {skipped}
    assert [(row["start"], row["sum"]) for row in after] == [(row["start"], row["sum"]) for row in before]


async def test_older_gaps_are_retried_every_six_hours_not_every_hour(recorder_mock, hass, enable_custom_integrations):
    yesterday = dt_util.now(BRISBANE).date() - timedelta(days=1)
    days = [yesterday - timedelta(days=n) for n in range(4, -1, -1)]
    skipped = days[2]
    _seed(hass, [day for day in days if day != skipped])

    with ExitStack() as stack:
        entry, coordinator, authenticate = await _setup_entry(
            hass, stack, published_days=set(days) - {skipped}
        )
        after_setup = authenticate.await_count

        for hour in range(24):
            await _retry_at_local_hour(hass, coordinator, hour)

        assert authenticate.await_count == after_setup + 4, "expected retries at local hours 0, 6, 12 and 18 only"
    await _unload(hass, entry)


async def test_the_retry_fills_the_day_once_nectr_publishes_it(recorder_mock, hass, enable_custom_integrations):
    yesterday = dt_util.now(BRISBANE).date() - timedelta(days=1)
    days = [yesterday - timedelta(days=n) for n in range(4, -1, -1)]
    skipped = days[2]
    _seed(hass, [day for day in days if day != skipped])
    published = set(days) - {skipped}

    with ExitStack() as stack:
        entry, coordinator, _authenticate = await _setup_entry(hass, stack, published_days=published)
        assert skipped not in _stored_days(await _stored_rows(hass))

        published.add(skipped)
        await _retry_at_local_hour(hass, coordinator, 6)
    await _unload(hass, entry)

    rows = await _stored_rows(hass)
    assert _stored_days(rows) == set(days)
    _assert_cumulative(rows)
