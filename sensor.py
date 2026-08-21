import re
from datetime import date
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, CURRENCY_DOLLAR
from .const import (
    DOMAIN,
    DEFAULT_VISIBLE_SENSORS,
    SENSOR_STATE_VISIBLE,
    SENSOR_STATE_HIDDEN,
    SENSOR_STATE_DISABLED,
    sensor_state_key,
)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = []
    
    for account_number in coordinator.data:
        entities.extend([
            NectrEnergySensor(coordinator, account_number, "Grid Consumption", "usage", "gridConsumption", "grid_consumption"),
            NectrEnergySensor(coordinator, account_number, "Export Consumption", "usage", "exportGridConsumption", "export_consumption"),
            NectrEnergySensor(coordinator, account_number, "Controlled Load", "usage", "controlledLoadConsumption", "controlled_load")
        ])
        
        entities.extend([
            NectrGenericSensor(coordinator, account_number, "Account Status", "account_info", "accountStatus", "account_status"),
            NectrGenericSensor(coordinator, account_number, "Plan Name", "account_info", "planName", "plan_name"),
            NectrGenericSensor(coordinator, account_number, "Billing Period Start", "account_info", "currentBillingPeriodStartDate", "billing_start", device_class=SensorDeviceClass.DATE),
            NectrGenericSensor(coordinator, account_number, "Billing Period End", "account_info", "currentBillingPeriodEndDate", "billing_end", device_class=SensorDeviceClass.DATE),
            NectrGenericSensor(coordinator, account_number, "Account Balance", "bill_info", "balance", "balance", device_class=SensorDeviceClass.MONETARY, uom=CURRENCY_DOLLAR),
            NectrGenericSensor(coordinator, account_number, "Power Perks Credit", "power_perks", "creditAmount", "power_perks_credit", device_class=SensorDeviceClass.MONETARY, uom=CURRENCY_DOLLAR),
            NectrGenericSensor(coordinator, account_number, "Power Perks Status", "power_perks", "statusText", "power_perks_status"),
        ])
        
        entities.extend([
            NectrTariffSensor(coordinator, account_number, "Tariff General Usage", "General usage charge", "tariff_general"),
            NectrTariffSensor(coordinator, account_number, "Tariff Solar Export", "Solar export to grid", "tariff_export"),
            NectrTariffSensor(coordinator, account_number, "Tariff Controlled Load", "Controlled load 2", "tariff_controlled_load"),
            NectrTariffSensor(coordinator, account_number, "Tariff Supply Charge", "Supply charge - General Usage", "tariff_supply"),
        ])

    for entity in entities:
        default_state = SENSOR_STATE_VISIBLE if entity.unique_key in DEFAULT_VISIBLE_SENSORS else SENSOR_STATE_HIDDEN
        state = entry.data.get(sensor_state_key(entity.unique_key), default_state)
        if state == SENSOR_STATE_DISABLED:
            entity._attr_entity_registry_enabled_default = False
        else:
            entity._attr_entity_registry_visible_default = state == SENSOR_STATE_VISIBLE

    async_add_entities(entities)

class NectrBaseSensor(SensorEntity):
    def __init__(self, coordinator, account_number, name, unique_key):
        self.coordinator = coordinator
        self.account_number = account_number
        self.unique_key = unique_key
        self._attr_name = f"Nectr {account_number} {name}"
        self._attr_unique_id = f"nectr_{account_number}_{unique_key}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.account_number)},
            "name": f"Nectr Account {self.account_number}",
            "manufacturer": "Nectr"
        }

class NectrEnergySensor(NectrBaseSensor):
    def __init__(self, coordinator, account_number, name, category, data_key, unique_key):
        super().__init__(coordinator, account_number, name, unique_key)
        self.category = category
        self.data_key = data_key
        self._attr_device_class = SensorDeviceClass.ENERGY
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    @property
    def native_value(self):
        data = self.coordinator.data.get(self.account_number, {}).get(self.category, {})
        node = data.get(self.data_key, {})
        return node.get("value")

class NectrGenericSensor(NectrBaseSensor):
    def __init__(self, coordinator, account_number, name, category, data_key, unique_key, device_class=None, uom=None):
        super().__init__(coordinator, account_number, name, unique_key)
        self.category = category
        self.data_key = data_key
        if device_class:
            self._attr_device_class = device_class
        if uom:
            self._attr_native_unit_of_measurement = uom

    @property
    def native_value(self):
        data = self.coordinator.data.get(self.account_number, {}).get(self.category, {})
        if not data:
            return None
        val = data.get(self.data_key)
        if val is None:
            return None
        if self._attr_device_class == SensorDeviceClass.MONETARY:
            try:
                return float(val)
            except ValueError:
                return val
        if self._attr_device_class == SensorDeviceClass.DATE:
            try:
                return date.fromisoformat(val)
            except ValueError:
                return None
        return val

class NectrTariffSensor(NectrBaseSensor):
    def __init__(self, coordinator, account_number, name, tariff_key, unique_key):
        super().__init__(coordinator, account_number, name, unique_key)
        self.tariff_key = tariff_key
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self):
        data = self.coordinator.data.get(self.account_number, {}).get("product_info", {})
        features = data.get("features", [])
        for feature in features:
            sub_features = feature.get("subFeature", [])
            if sub_features:
                for sf in sub_features:
                    if sf.get("key") == self.tariff_key:
                        val_str = sf.get("value", "")
                        match = re.search(r"([0-9.]+)", val_str)
                        if match:
                            return float(match.group(1))
        return None

    @property
    def native_unit_of_measurement(self):
        data = self.coordinator.data.get(self.account_number, {}).get("product_info", {})
        features = data.get("features", [])
        for feature in features:
            sub_features = feature.get("subFeature", [])
            if sub_features:
                for sf in sub_features:
                    if sf.get("key") == self.tariff_key:
                        val_str = sf.get("value", "")
                        if "c/kWh" in val_str:
                            return "c/kWh"
                        if "c/day" in val_str:
                            return "c/day"
        return None