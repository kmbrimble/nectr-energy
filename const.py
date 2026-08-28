DOMAIN = "nectr"
CONF_INTERVAL = "interval"
DEFAULT_INTERVAL = 24
INTERVAL_OPTIONS = [1, 3, 6, 12, 24]

SERVICE_BACKFILL_HISTORY = "backfill_history"
BACKFILL_INITIAL_DAYS = 365
# ponytail: hard ceiling on a manually requested backfill so a typo (e.g. days=100000) can't
# turn into tens of thousands of sequential API calls. Raise if longer history is ever needed.
MAX_BACKFILL_DAYS = 1095

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
    "power_perks_percentage": "Power Perks Progress",
    "tariff_general": "Tariff General Usage",
    "tariff_export": "Tariff Solar Export",
    "tariff_controlled_load": "Tariff Controlled Load",
    "tariff_supply": "Tariff Supply Charge",
    "total_due": "Total Due",
    "next_scheduled_payment_date": "Next Scheduled Payment Date",
    "direct_debit_amount": "Direct Debit Amount",
    "direct_debit_date": "Direct Debit Date",
    "nmi": "Meter Identifier",
}

DEFAULT_VISIBLE_SENSORS = ["grid_consumption", "export_consumption", "controlled_load"]

DEFAULT_DISABLED_SENSORS = ["account_status", "plan_name", "power_perks_status"]


def sensor_state_key(sensor_key: str) -> str:
    return f"sensor_state_{sensor_key}"