import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from .const import DOMAIN, SERVICE_BACKFILL_HISTORY, BACKFILL_INITIAL_DAYS, MAX_BACKFILL_DAYS
from .coordinator import NectrDataUpdateCoordinator

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NectrDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if not await coordinator.async_has_existing_statistics():
        hass.async_create_task(coordinator.async_backfill_history())

    _async_register_services(hass)
    return True

def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_BACKFILL_HISTORY):
        return

    async def handle_backfill_history(call: ServiceCall) -> None:
        days = call.data.get("days", BACKFILL_INITIAL_DAYS)
        for coordinator in hass.data.get(DOMAIN, {}).values():
            await coordinator.async_backfill_history(days)

    hass.services.async_register(
        DOMAIN,
        SERVICE_BACKFILL_HISTORY,
        handle_backfill_history,
        schema=vol.Schema({
            vol.Optional("days", default=BACKFILL_INITIAL_DAYS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_BACKFILL_DAYS)
            )
        })
    )

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_BACKFILL_HISTORY)
    return unload_ok
