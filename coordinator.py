import logging
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import aiohttp
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import async_import_statistics
from homeassistant.const import UnitOfEnergy
from homeassistant.util import dt as dt_util
from .api import NectrApiClient
from .const import DOMAIN, CONF_INTERVAL

_LOGGER = logging.getLogger(__name__)

class NectrDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self.api = NectrApiClient(entry.data["email"], entry.data["password"])
        interval_hours = entry.data.get(CONF_INTERVAL, 24)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(hours=interval_hours))

    async def _async_update_data(self):
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
                
                await self._inject_historical_data(acc_num, usage)
            return data

    async def _inject_historical_data(self, account_number, usage_data):
        if not usage_data:
            return
        all_usage = usage_data.get("allUsage", [])
        if not all_usage:
            return

        tz = ZoneInfo("Australia/Brisbane")
        now = dt_util.now(tz)
        yesterday = (now - timedelta(days=1)).date()

        metrics = {
            "grid_consumption": "gridUsage",
            "export_consumption": "exportUsage",
            "controlled_load": "controlLoadUsage"
        }

        for metric_key, usage_key in metrics.items():
            statistic_id = f"sensor.nectr_{account_number.lower().replace('-', '_')}_{metric_key}"
            metadata = StatisticMetaData(
                has_mean=False,
                has_sum=True,
                name=f"Nectr {account_number} {metric_key.replace('_', ' ').title()}",
                source=DOMAIN,
                statistic_id=statistic_id,
                unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR
            )

            statistics = []
            running_sum = 0.0
            
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