"""Guards the real initial-backfill feature: a fresh install must import more
than a single day of history, an already-installed integration must be able to
re-run a full backfill on demand via a service, and that service must clear
existing statistics before re-importing (splicing older data in front of an
existing cumulative `sum` series would make it non-monotonic)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from const import DOMAIN, BACKFILL_INITIAL_DAYS, MAX_BACKFILL_DAYS, SERVICE_BACKFILL_HISTORY


def demo():
    assert BACKFILL_INITIAL_DAYS > 30, "initial backfill must cover far more than the old single-day default"
    assert MAX_BACKFILL_DAYS >= BACKFILL_INITIAL_DAYS
    assert SERVICE_BACKFILL_HISTORY == "backfill_history"

    coordinator_source = (ROOT / "coordinator.py").read_text()
    assert "async def async_backfill_history" in coordinator_source
    assert "async def async_has_existing_statistics" in coordinator_source
    assert "async_clear_statistics(" in coordinator_source, (
        "backfill must clear existing statistics before re-importing, since splicing older "
        "data in front of an existing cumulative sum series would make it non-monotonic"
    )
    assert "async_add_executor_job(\n            clear_statistics" not in coordinator_source, (
        "regression guard: statistics.clear_statistics() asserts it runs on the recorder's own "
        "thread — running it via async_add_executor_job uses the generic executor pool instead "
        "and raises 'Detected unsafe call not in recorder thread'. Use "
        "Recorder.async_clear_statistics() (a queued task) instead."
    )
    assert "has_mean=" not in coordinator_source, (
        "regression guard: has_mean is deprecated in favour of mean_type and logs a removal "
        "warning (HA 2026.11) — use StatisticMeanType.NONE instead"
    )
    assert "StatisticMeanType.NONE" in coordinator_source

    init_source = (ROOT / "__init__.py").read_text()
    assert "SERVICE_BACKFILL_HISTORY" in init_source
    assert "async_has_existing_statistics" in init_source, (
        "the automatic backfill must be gated on there being no existing statistics yet, "
        "so it doesn't refire a full re-import on every HA restart/reload"
    )
    assert "hass.services.has_service" in init_source, "service registration must be idempotent across entry reloads"
    assert "async_remove" in init_source, "service should be cleaned up when the last entry unloads"

    services_yaml = (ROOT / "services.yaml").read_text()
    assert re.search(r"^backfill_history:", services_yaml, re.M)
    assert "days" in services_yaml

    print("ok")


if __name__ == "__main__":
    demo()
