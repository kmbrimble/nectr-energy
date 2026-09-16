"""Guards the fix for history corrupted by the recorder: hourly history must go into
external statistics (source `nectr`) under a valid statistic id, the energy sensors must not
carry a state_class (which made the recorder compile competing statistics for the same id),
and a backfill must produce one monotonic series without warning about pre-supply days.

Also guards the getMyProductInfo schema drift: the server dropped two fields and rejected the
whole query with HTTP 400, which kept the integration in setup_retry."""
import asyncio
import importlib.util
import logging
import re
import sys
import types
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Copied from homeassistant/components/recorder/statistics.py (2026.9.0) VALID_STATISTIC_ID.
VALID_STATISTIC_ID = re.compile(r"^(?!.+__)(?!_)[\da-z_]+(?<!_):(?!_)[\da-z_]+(?<!_)$")

imported = []
cleared = []


def _stub(name, **attrs):
    module = types.ModuleType(name)
    module.__dict__.update(attrs)
    sys.modules[name] = module
    return module


class _Enum:
    NONE = 0


class _Coordinator:
    def __init__(self, *args, **kwargs):
        pass


class _Instance:
    def async_clear_statistics(self, ids, on_done):
        cleared.append(list(ids))
        on_done()


def _load_coordinator():
    for name in ("homeassistant", "homeassistant.helpers", "homeassistant.components",
                 "homeassistant.components.recorder.models", "homeassistant.util"):
        _stub(name)
    _stub("aiohttp", ClientError=Exception, ClientSession=object)
    _stub("homeassistant.helpers.update_coordinator",
          DataUpdateCoordinator=_Coordinator, UpdateFailed=Exception)
    _stub("homeassistant.components.recorder", get_instance=lambda hass: _Instance())
    sys.modules["homeassistant.components.recorder.models"].__dict__.update(
        StatisticData=dict, StatisticMeanType=_Enum, StatisticMetaData=dict)
    _stub("homeassistant.components.recorder.statistics",
          async_add_external_statistics=lambda hass, meta, stats: imported.append((meta, stats)),
          get_last_statistics=None)
    _stub("homeassistant.const", UnitOfEnergy=types.SimpleNamespace(KILO_WATT_HOUR="kWh"))
    _stub("homeassistant.util.dt",
          now=lambda tz: datetime(2026, 9, 16, 12, tzinfo=tz),
          utc_from_timestamp=lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc))
    sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]

    package = _stub("nectr")
    package.__path__ = [str(ROOT)]
    for mod in ("const", "api", "coordinator"):
        spec = importlib.util.spec_from_file_location(f"nectr.{mod}", ROOT / f"{mod}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"nectr.{mod}"] = module
        spec.loader.exec_module(module)
    return sys.modules["nectr.coordinator"]


class _FakeApi:
    """Supply starts 2026-09-13; one gap on 2026-09-14."""

    def __init__(self):
        self.calls = []

    async def get_usage(self, session, account_number, from_date, to_date):
        self.calls.append((from_date, to_date))
        day = datetime.strptime(from_date, "%d/%m/%Y").date()
        if day < date(2026, 9, 13) or day == date(2026, 9, 14):
            return {"allUsage": []}
        # Newest-first and "9:00"-style periods, as the live API returns them.
        return {"allUsage": [
            {"period": f"{h}:00", "gridUsage": 0.5, "exportUsage": 0.1 if h == 12 else 0,
             "controlLoadUsage": None}
            for h in reversed(range(24))
        ]}


class _Hass:
    class loop:
        @staticmethod
        def call_soon_threadsafe(fn):
            fn()


def test_demo():
    coordinator = _load_coordinator()

    for account in ("A-6CFFE20E", "12345678", "_x__y_", 9876):
        for metric in coordinator.METRICS:
            statistic_id = coordinator.external_statistic_id(account, metric)
            assert VALID_STATISTIC_ID.match(statistic_id), statistic_id
            assert statistic_id.startswith("nectr:")
    assert coordinator.external_statistic_id("A-6CFFE20E", "grid_consumption") == \
        "nectr:a_6cffe20e_grid_consumption"

    meta = coordinator._statistic_metadata("A-1", "controlled_load")
    assert meta["source"] == "nectr", "external statistics need source == the id's domain"
    assert meta["unit_class"] == "energy", "omitting unit_class breaks in HA 2026.11"
    assert meta["has_sum"] is True

    fake = object.__new__(coordinator.NectrDataUpdateCoordinator)
    fake.hass = _Hass()
    fake.api = _FakeApi()
    warnings = []
    handler = logging.Handler()
    handler.emit = lambda record: warnings.append(record.getMessage())
    coordinator._LOGGER.addHandler(handler)
    asyncio.run(fake._backfill_account(None, "A-1", "QUEENSLAND", 5))

    assert cleared == [[coordinator.external_statistic_id("A-1", m) for m in coordinator.METRICS]]
    assert fake.api.calls[0] == ("11/09/2026", "12/09/2026"), fake.api.calls[0]
    assert len(fake.api.calls) == 5
    assert len(warnings) == 1 and "2026-09-14" in warnings[0], warnings

    by_id = {m["statistic_id"]: s for m, s in imported}
    grid = by_id["nectr:a_1_grid_consumption"]
    assert len(grid) == 48, "two days with data, 24 hours each"
    assert [s["start"].hour for s in grid[:24]] == list(range(24)), "hours sorted ascending"
    sums = [s["sum"] for s in grid]
    assert sums == sorted(sums) and abs(sums[-1] - 24.0) < 1e-9
    assert grid[0]["start"].utcoffset() == timedelta(hours=10)
    assert abs(by_id["nectr:a_1_export_consumption"][-1]["sum"] - 0.2) < 1e-9
    assert by_id["nectr:a_1_controlled_load"][-1]["sum"] == 0.0, "null usage counts as zero"

    sensor_source = (ROOT / "sensor.py").read_text()
    energy_sensor = sensor_source.split("class NectrEnergySensor")[1].split("\nclass ")[0]
    assert "_attr_state_class" not in energy_sensor

    api_source = (ROOT / "api.py").read_text()
    assert "isEligibleForUpdate" not in api_source and "isOnBestOffer" not in api_source
    assert "response.raise_for_status()" not in api_source, "the 400 body names the failing field; keep it"

    print("ok")


if __name__ == "__main__":
    test_demo()
