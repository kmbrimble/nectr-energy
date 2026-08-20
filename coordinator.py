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

                    await self._inject_historical_data(acc_num, account.get("state"), usage)
                return data
        except (aiohttp.ClientError, ValueError) as err:
            raise UpdateFailed(f"Error communicating with Nectr API: {err}") from err

    async def _inject_historical_data(self, account_number, account_state, usage_data):
        if not usage_data:
            return
        all_usage = usage_data.get("allUsage", [])
        if not all_usage:
            return

        # ponytail: assumes the API's usage response always covers exactly
        # "yesterday" relative to poll time; a missed poll only backfills the
        # most recent day, not any gap. Add gap catch-up if that's needed.
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
            running_sum = last_stats[statistic_id][0]["sum"] if statistic_id in last_stats else 0.0

            statistics = []

            sorted_usage = sorted(all_usage, key=lambda x: int(x["period"].split(":")[0]))

            for item in sorted_usage:
                hour = int(item["period"].split(":")[0])
                start_time = datetime.combine(yesterday, datetime.min.time(), tzinfo=tz).replace(hour=hour)
                val = item.get(usage_key, 0) or 0
                running_sum += float(val)
                
                statistics.append(StatisticData(
                    start=start_time,
                    state=val,
                    sum=running_sum
                ))

            async_import_statistics(self.hass, metadata, statistics)