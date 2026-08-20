DOMAIN = "nectr"
CONF_INTERVAL = "interval"
DEFAULT_INTERVAL = 24

CONF_VISIBLE_SENSORS = "visible_sensors"
CONF_DISABLED_SENSORS = "disabled_sensors"

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