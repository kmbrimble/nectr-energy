import asyncio
import logging
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import aiohttp
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics, get_last_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.util import dt as dt_util
from .api import NectrApiClient
from .const import DOMAIN, CONF_INTERVAL, DEFAULT_INTERVAL, BACKFILL_INITIAL_DAYS

METRICS = {
    "grid_consumption": "gridUsage",
    "export_consumption": "exportUsage",
    "controlled_load": "controlLoadUsage"
}

CLEAR_STATISTICS_TIMEOUT = 10

_LOGGER = logging.getLogger(__name__)

STATE_TIMEZONES = {
    "NEW SOUTH WALES": "Australia/Sydney",
    "AUSTRALIAN CAPITAL TERRITORY": "Australia/Sydney",
    "VICTORIA": "Australia/Melbourne",
    "QUEENSLAND": "Australia/Brisbane",
    "SOUTH AUSTRALIA": "Australia/Adelaide",
    "WESTERN AUSTRALIA": "Australia/Perth",
    "TASMANIA": "Australia/Hobart",
    "NORTHERN TERRITORY": "Australia/Darwin",
}

class NectrDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self.api = NectrApiClient(entry.data["email"], entry.data["password"])
        interval_hours = entry.options.get(CONF_INTERVAL, entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL))
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=interval_hours))

    async def _async_update_data(self):
        try:
            async with aiohttp.ClientSession() as session:
                await self.api.authenticate(session)
                accounts = await self.api.get_accounts(session)

                data = {}
                for account in accounts:
                    acc_num = account["number"]

                    usage = await self.api.get_usage(session, acc_num)
                    account_info = await self.api.get_account_info(session, acc_num)
                    power_perks = await self.api.get_power_perks(session, acc_num)
                    bill_info = await self.api.get_bill_payment_info(session, acc_num)
                    product_info = await self.api.get_product_info(session, acc_num)

                    data[acc_num] = {
                        "usage": usage,
                        "account_info": account_info,
                        "power_perks": power_perks,
                        "bill_info": bill_info,
                        "product_info": product_info
                    }

                    await self._inject_historical_data(session, acc_num, account.get("state"))
                return data
        except (aiohttp.ClientError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with Nectr API: {err}") from err

    async def _inject_historical_data(self, session, account_number, account_state):
        tz = ZoneInfo(STATE_TIMEZONES.get((account_state or "").upper(), "Australia/Brisbane"))
        now = dt_util.now(tz)
        yesterday = (now - timedelta(days=1)).date()

        registry = er.async_get(self.hass)

        for metric_key, usage_key in METRICS.items():
            unique_id = f"nectr_{account_number}_{metric_key}"
            statistic_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            if statistic_id is None:
                continue

            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Nectr {account_number} {metric_key.replace('_', ' ').title()}",
                source="recorder",
                statistic_id=statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR
            )

            last_stats = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
            )
            if statistic_id in last_stats:
                last_entry = last_stats[statistic_id][0]
                running_sum = last_entry["sum"] or 0.0
                last_date = dt_util.utc_from_timestamp(last_entry["start"]).astimezone(tz).date()
            else:
                running_sum = 0.0
                last_date = None

            statistics = []

            for day in _missing_dates(last_date, yesterday):
                day_data = await self.api.get_usage(
                    session,
                    account_number,
                    day.strftime("%d/%m/%Y"),
                    (day + timedelta(days=1)).strftime("%d/%m/%Y"),
                )
                day_usage = day_data.get("allUsage", [])
                if not day_usage:
                    continue

                sorted_usage = sorted(day_usage, key=lambda x: int(x["period"].split(":")[0]))

                for item in sorted_usage:
                    hour = int(item["period"].split(":")[0])
                    start_time = datetime.combine(day, datetime.min.time(), tzinfo=tz).replace(hour=hour)
                    val = item.get(usage_key, 0) or 0
                    running_sum += float(val)

                    statistics.append(StatisticData(
                        start=start_time,
                        state=val,
                        sum=running_sum
                    ))

            if statistics:
                async_import_statistics(self.hass, metadata, statistics)

    async def async_has_existing_statistics(self) -> bool:
        """Whether any tracked metric already has statistics, for any account.

        Gates the one-time automatic backfill so it only fires on a genuinely fresh
        install, not on every HA restart/reload of an already-populated entry.
        """
        if not self.data:
            return False
        registry = er.async_get(self.hass)
        instance = get_instance(self.hass)
        for acc_num in self.data:
            for metric_key in METRICS:
                statistic_id = registry.async_get_entity_id("sensor", DOMAIN, f"nectr_{acc_num}_{metric_key}")
                if statistic_id is None:
                    continue
                last_stats = await instance.async_add_executor_job(
                    get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
                )
                if statistic_id in last_stats:
                    return True
        return False

    async def async_backfill_history(self, days: int = BACKFILL_INITIAL_DAYS) -> None:
        """Wipe and re-import `days` of hourly history for every tracked metric.

        Used both for the one-time automatic backfill on fresh install and for the
        on-demand `nectr.backfill_history` service. Clears existing statistics first
        rather than splicing older data in front of what's already there — HA statistics
        require a monotonically increasing cumulative `sum`, and a freshly computed
        earlier window starting its own sum from 0 would create a discontinuity against
        whatever sum the existing data already reached.
        """
        async with aiohttp.ClientSession() as session:
            await self.api.authenticate(session)
            accounts = await self.api.get_accounts(session)
            for account in accounts:
                await self._backfill_account(session, account["number"], account.get("state"), days)

    async def _async_clear_statistics(self, statistic_ids: list[str]) -> None:
        """Clear statistics via the recorder's own queued task, not a generic executor thread.

        `statistics.clear_statistics()` asserts it's running on the recorder's dedicated
        thread; calling it through `async_add_executor_job` uses the general executor pool
        instead and trips that assertion. `Recorder.async_clear_statistics()` queues the
        work correctly — it's fire-and-forget, so wait on its `on_done` callback like HA's
        own `recorder/clear_statistics` websocket handler does.
        """
        done = asyncio.Event()
        get_instance(self.hass).async_clear_statistics(
            statistic_ids, on_done=lambda: self.hass.loop.call_soon_threadsafe(done.set)
        )
        try:
            async with asyncio.timeout(CLEAR_STATISTICS_TIMEOUT):
                await done.wait()
        except TimeoutError:
            _LOGGER.warning("Timed out clearing statistics for %s before backfill", statistic_ids)

    async def _backfill_account(self, session, account_number, account_state, days):
        tz = ZoneInfo(STATE_TIMEZONES.get((account_state or "").upper(), "Australia/Brisbane"))
        yesterday = (dt_util.now(tz) - timedelta(days=1)).date()
        start_day = yesterday - timedelta(days=days - 1)

        registry = er.async_get(self.hass)
        tracked = {}
        for metric_key, usage_key in METRICS.items():
            statistic_id = registry.async_get_entity_id("sensor", DOMAIN, f"nectr_{account_number}_{metric_key}")
            if statistic_id is None:
                continue
            tracked[metric_key] = {
                "usage_key": usage_key,
                "statistic_id": statistic_id,
                "metadata": StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    name=f"Nectr {account_number} {metric_key.replace('_', ' ').title()}",
                    source="recorder",
                    statistic_id=statistic_id,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR
                ),
                "running_sum": 0.0,
                "statistics": [],
            }

        if not tracked:
            return

        await self._async_clear_statistics([t["statistic_id"] for t in tracked.values()])

        for i in range(days):
            day = start_day + timedelta(days=i)
            day_data = await self.api.get_usage(
                session,
                account_number,
                day.strftime("%d/%m/%Y"),
                (day + timedelta(days=1)).strftime("%d/%m/%Y"),
            )
            day_usage = day_data.get("allUsage", [])
            if not day_usage:
                continue

            sorted_usage = sorted(day_usage, key=lambda x: int(x["period"].split(":")[0]))

            for item in sorted_usage:
                hour = int(item["period"].split(":")[0])
                start_time = datetime.combine(day, datetime.min.time(), tzinfo=tz).replace(hour=hour)
                for metric in tracked.values():
                    val = item.get(metric["usage_key"], 0) or 0
                    metric["running_sum"] += float(val)
                    metric["statistics"].append(StatisticData(
                        start=start_time,
                        state=val,
                        sum=metric["running_sum"]
                    ))

        for metric in tracked.values():
            if metric["statistics"]:
                async_import_statistics(self.hass, metric["metadata"], metric["statistics"])


def _missing_dates(last_date, until_date, max_days=30):
    """Days needing backfill, from the day after last_date through until_date inclusive.

    Capped at max_days so a very long outage doesn't trigger an unbounded run of API calls;
    anything older is left ungraphed (ponytail: raise max_days, or page further back, if a
    longer catch-up window is ever needed).
    """
    if last_date is None:
        return [until_date]
    if last_date >= until_date:
        return []
    start = max(last_date + timedelta(days=1), until_date - timedelta(days=max_days - 1))
    return [start + timedelta(days=i) for i in range((until_date - start).days + 1)]


def _demo():
    from datetime import date, timezone

    # Regression guard for #33: get_last_statistics()'s "start" is a raw float
    # Unix timestamp, not a datetime, so it must be converted before .astimezone().
    raw_start_ts = 1755561600.0  # 2025-08-19T00:00:00Z
    converted = datetime.fromtimestamp(raw_start_ts, tz=timezone.utc)
    assert converted.astimezone(ZoneInfo("Australia/Brisbane")).date() == date(2025, 8, 19)
    assert not hasattr(raw_start_ts, "astimezone")

    y = date(2026, 8, 19)
    assert _missing_dates(None, y) == [y]
    assert _missing_dates(y, y) == []
    assert _missing_dates(y - timedelta(days=1), y) == [y]
    assert _missing_dates(y - timedelta(days=3), y) == [
        y - timedelta(days=2), y - timedelta(days=1), y
    ]
    assert len(_missing_dates(y - timedelta(days=400), y)) == 30
    assert _missing_dates(y - timedelta(days=400), y)[-1] == y


if __name__ == "__main__":
    _demo()
    print("ok")