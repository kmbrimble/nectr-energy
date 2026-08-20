import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
import aiohttp
from .const import DOMAIN, CONF_INTERVAL, DEFAULT_INTERVAL
from .api import NectrApiClient

class NectrConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
                        return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)
            except Exception:
                errors["base"] = "auth_error"

        schema = vol.Schema({
            vol.Required(CONF_EMAIL): str,
            vol.Required(CONF_PASSWORD): str,
            vol.Required(CONF_INTERVAL, default=DEFAULT_INTERVAL): vol.In([1, 3, 6, 12, 24])
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)