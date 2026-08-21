DOMAIN = "nectr"
CONF_INTERVAL = "interval"
DEFAULT_INTERVAL = 24
INTERVAL_OPTIONS = [1, 3, 6, 12, 24]

SENSOR_STATE_VISIBLE = "visible"
SENSOR_STATE_HIDDEN = "hidden"
SENSOR_STATE_DISABLED = "disabled"

SENSOR_CATALOG = {
    "grid_consumption": "Grid Consumption",
    "export_consumption": "Export Consumption",
    "controlled_load": "Controlled Load",
    "account_status": "Account Status",
    "plan_name": "Plan Name",
    "billing_start": "Billing Period Start",
    "billing_end": "Billing Period End",
    "balance": "Account Balance",
    "power_perks_credit": "Power Perks Credit",
    "power_perks_status": "Power Perks Status",
    "tariff_general": "Tariff General Usage",
    "tariff_export": "Tariff Solar Export",
    "tariff_controlled_load": "Tariff Controlled Load",
    "tariff_supply": "Tariff Supply Charge",
}

DEFAULT_VISIBLE_SENSORS = ["grid_consumption", "export_consumption", "controlled_load"]


def sensor_state_key(sensor_key: str) -> str:
    return f"sensor_state_{sensor_key}"