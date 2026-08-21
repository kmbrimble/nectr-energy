import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
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
    INTERVAL_OPTIONS,
    DEFAULT_VISIBLE_SENSORS,
    SENSOR_CATALOG,
    SENSOR_STATE_VISIBLE,
    SENSOR_STATE_HIDDEN,
    SENSOR_STATE_DISABLED,
    sensor_state_key,
)
from .api import NectrApiClient


def _interval_selector() -> vol.All:
    options = [SelectOptionDict(value=str(value), label=str(value)) for value in INTERVAL_OPTIONS]
    return vol.All(
        SelectSelector(SelectSelectorConfig(options=options, mode=SelectSelectorMode.DROPDOWN)),
        vol.Coerce(int),
    )


class NectrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._account_data = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NectrOptionsFlow()

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
                        await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                        self._abort_if_unique_id_configured()
                        self._account_data = user_input
                        return await self.async_step_sensors()
            except Exception:
                errors["base"] = "auth_error"

        schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_sensors(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=self._account_data[CONF_EMAIL],
                data={**self._account_data, CONF_INTERVAL: DEFAULT_INTERVAL, **user_input},
            )

        state_options = [
            SelectOptionDict(value=SENSOR_STATE_VISIBLE, label="Visible"),
            SelectOptionDict(value=SENSOR_STATE_HIDDEN, label="Hidden"),
            SelectOptionDict(value=SENSOR_STATE_DISABLED, label="Disabled"),
        ]
        schema = vol.Schema({
            vol.Required(
                sensor_state_key(key),
                default=SENSOR_STATE_VISIBLE if key in DEFAULT_VISIBLE_SENSORS else SENSOR_STATE_HIDDEN,
            ): SelectSelector(
                SelectSelectorConfig(options=state_options, mode=SelectSelectorMode.DROPDOWN)
            )
            for key in SENSOR_CATALOG
        })
        return self.async_show_form(step_id="sensors", data_schema=schema)


class NectrOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_INTERVAL, self.config_entry.data.get(CONF_INTERVAL, DEFAULT_INTERVAL)
        )
        schema = vol.Schema({
            vol.Required(CONF_INTERVAL, default=str(current)): _interval_selector(),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
