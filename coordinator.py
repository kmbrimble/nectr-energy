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
from .const import DOMAIN, CONF_INTERVAL

_LOGGER = logging.getLogger(__name__)

STATE_TIMEZONES = {
    "NSW": "Australia/Sydney",
    "ACT": "Australia/Sydney",
    "VIC": "Australia/Melbourne",
    "QLD": "Australia/Brisbane",
    "SA": "Australia/Adelaide",
    "WA": "Australia/Perth",
    "TAS": "Australia/Hobart",
    "NT": "Australia/Darwin",
}

class NectrDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self.api = NectrApiClient(entry.data["email"], entry.data["password"])
        interval_hours = entry.data.get(CONF_INTERVAL, 24)
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

                    await self._inject_historical_data(session, acc_num, account.get("state"), usage)
                return data
        except (aiohttp.ClientError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with Nectr API: {err}") from err

    async def _inject_historical_data(self, session, account_number, account_state, usage_data):
        if not usage_data:
            return
        all_usage = usage_data.get("allUsage", [])
        if not all_usage:
            return

        tz = ZoneInfo(STATE_TIMEZONES.get(account_state, "Australia/Brisbane"))
        now = dt_util.now(tz)
        yesterday = (now - timedelta(days=1)).date()

        metrics = {
            "grid_consumption": "gridUsage",
            "export_consumption": "exportUsage",
            "controlled_load": "controlLoadUsage"
        }

        registry = er.async_get(self.hass)

        for metric_key, usage_key in metrics.items():
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
                last_date = last_entry["start"].astimezone(tz).date()
            else:
                running_sum = 0.0
                last_date = None

            statistics = []

            for day in _missing_dates(last_date, yesterday):
                if day == yesterday:
                    day_usage = all_usage
                else:
                    day_data = await self.api.get_usage(session, account_number, day.isoformat(), day.isoformat())
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
    from datetime import date
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