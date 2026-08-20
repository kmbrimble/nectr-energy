import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)
import aiohttp
from .const import (
    DOMAIN,
    CONF_INTERVAL,
    DEFAULT_INTERVAL,
    CONF_VISIBLE_SENSORS,
    CONF_DISABLED_SENSORS,
    DEFAULT_VISIBLE_SENSORS,
    SENSOR_CATALOG,
)
from .api import NectrApiClient

class NectrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._account_data = None

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = NectrApiClient(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            try:
                async with aiohttp.ClientSession() as session:
                    await api.authenticate(session)
                    accounts = await api.get_accounts(session)
                    if not accounts:
                        errors["base"] = "no_active_accounts"
                    else:
                        self._account_data = user_input
                        return await self.async_step_sensors()
            except Exception:
                errors["base"] = "auth_error"

        schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): vol.In([1, 3, 6, 12, 24])
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensors(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=self._account_data[CONF_EMAIL],
                data={**self._account_data, **user_input},
            )

        sensor_options = [
            SelectOptionDict(value=key, label=label) for key, label in SENSOR_CATALOG.items()
        ]
        schema = vol.Schema({
            vol.Optional(CONF_VISIBLE_SENSORS, default=DEFAULT_VISIBLE_SENSORS): SelectSelector(
                SelectSelectorConfig(options=sensor_options, multiple=True, mode=SelectSelectorMode.LIST)
            ),
            vol.Optional(CONF_DISABLED_SENSORS, default=[]): SelectSelector(
                SelectSelectorConfig(options=sensor_options, multiple=True, mode=SelectSelectorMode.LIST)
            ),
        })
        return self.async_show_form(step_id="sensors", data_schema=schema)