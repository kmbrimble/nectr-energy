"""Regression guard for #36: historical injection was skipping yesterday's real
per-day HOURLY fetch and reusing the no-date-range usage blob instead, which the
live API only returns as daily-aggregate data for, not hourly."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def demo():
    source = (ROOT / "coordinator.py").read_text()

    inject_match = re.search(
        r"    async def _inject_historical_data\(.*?\n(?=    (?:async )?def\s|\Z)",
        source,
        re.S,
    )
    assert inject_match, "_inject_historical_data not found in coordinator.py"
    inject_source = inject_match.group(0)

    signature = inject_source.splitlines()[0]
    assert "usage_data" not in signature, (
        "_inject_historical_data should no longer take a usage_data param — "
        "every day must be fetched explicitly, not shortcut from a passed-in blob"
    )
    assert "day == yesterday" not in inject_source, (
        "no special-casing for yesterday — it must go through the same "
        "explicit-date-range get_usage() fetch as every other backfill day"
    )
    assert inject_source.count("self.api.get_usage(") == 1, (
        "expected exactly one get_usage() call site inside the per-day loop"
    )

    call_site = re.search(r"await self\._inject_historical_data\([^)]*\)", source)
    assert call_site, "_inject_historical_data call site not found"
    assert "usage" not in call_site.group(0).split(",")[-1], (
        "call site should no longer pass the no-date-range usage blob into injection"
    )

    print("ok")


if __name__ == "__main__":
    demo()
