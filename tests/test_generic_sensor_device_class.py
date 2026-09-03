"""Guards the AttributeError from #30: HA's Entity._attr_device_class has no
class-level default (bare annotation, not `= None`), so a sensor that never
sets it crashes on read instead of returning None. NectrGenericSensor must
always set the instance attribute, even when device_class isn't passed."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Minimal stand-ins so sensor.py imports without the real homeassistant package.
ha_components_sensor = type(sys)("homeassistant.components.sensor")


class _FakeStrEnum(str):
    def __eq__(self, other):
        return str(self) == str(other)

    __hash__ = str.__hash__


class _SensorDeviceClass:
    MONETARY = _FakeStrEnum("monetary")
    DATE = _FakeStrEnum("date")
    ENERGY = _FakeStrEnum("energy")


ha_components_sensor.SensorEntity = object
ha_components_sensor.SensorDeviceClass = _SensorDeviceClass
ha_components_sensor.SensorStateClass = MagicMock(TOTAL="total")
sys.modules["homeassistant"] = type(sys)("homeassistant")
sys.modules["homeassistant.components"] = type(sys)("homeassistant.components")
sys.modules["homeassistant.components.sensor"] = ha_components_sensor
ha_const = type(sys)("homeassistant.const")
ha_const.UnitOfEnergy = MagicMock(KILO_WATT_HOUR="kWh")
ha_const.CURRENCY_DOLLAR = "$"
ha_const.PERCENTAGE = "%"
sys.modules["homeassistant.const"] = ha_const

import importlib.util

ROOT = Path(__file__).resolve().parent.parent
pkg = type(sys)("nectr")
pkg.__path__ = [str(ROOT)]
sys.modules["nectr"] = pkg

spec = importlib.util.spec_from_file_location("nectr.sensor", ROOT / "sensor.py", submodule_search_locations=[])
sensor_module = importlib.util.module_from_spec(spec)
sensor_module.__package__ = "nectr"
sys.modules["nectr.sensor"] = sensor_module
spec.loader.exec_module(sensor_module)


def test_demo():
    class FakeCoordinator:
        data = {"acc1": {"account_info": {"planName": "Some Plan"}}}

    s = sensor_module.NectrGenericSensor(
        FakeCoordinator(), "acc1", "Plan Name", "account_info", "planName", "plan_name"
    )
    assert s.native_value == "Some Plan"

    print("ok")


if __name__ == "__main__":
    test_demo()
