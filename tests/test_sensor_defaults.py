"""Guards two things: (1) the visible/disabled/hidden default logic picks the
right bucket, and (2) every SENSOR_CATALOG key actually has a matching
unique_key wired up in sensor.py (a typo here silently drops the sensor's
config-flow toggle and translation label)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from const import (
    SENSOR_CATALOG,
    DEFAULT_VISIBLE_SENSORS,
    DEFAULT_DISABLED_SENSORS,
    SENSOR_STATE_VISIBLE,
    SENSOR_STATE_HIDDEN,
    SENSOR_STATE_DISABLED,
)


def default_sensor_state(key):
    if key in DEFAULT_VISIBLE_SENSORS:
        return SENSOR_STATE_VISIBLE
    if key in DEFAULT_DISABLED_SENSORS:
        return SENSOR_STATE_DISABLED
    return SENSOR_STATE_HIDDEN


def demo():
    assert default_sensor_state("grid_consumption") == SENSOR_STATE_VISIBLE
    assert default_sensor_state("account_status") == SENSOR_STATE_DISABLED
    assert default_sensor_state("plan_name") == SENSOR_STATE_DISABLED
    assert default_sensor_state("power_perks_status") == SENSOR_STATE_DISABLED
    assert default_sensor_state("total_due") == SENSOR_STATE_HIDDEN
    assert default_sensor_state("nmi") == SENSOR_STATE_HIDDEN

    sensor_source = (ROOT / "sensor.py").read_text()
    unique_keys = set(re.findall(r'"([a-z][a-z_]*)"', sensor_source))
    for key in SENSOR_CATALOG:
        assert key in unique_keys, f"{key} in SENSOR_CATALOG has no matching unique_key in sensor.py"

    print("ok")


if __name__ == "__main__":
    demo()
