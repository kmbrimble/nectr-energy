# Project Instructions

Home Assistant custom integration (domain: `nectr`) for the Nectr Energy GraphQL API.
Flat file layout at repo root (not nested under `custom_components/`) — this *is* the
component directory. No packaging metadata or dependency file: HA supplies `homeassistant`,
`aiohttp` and `voluptuous` at runtime. Code style: `.claude/rules/code-quality.md`.

## Architecture

- `api.py` — `NectrApiClient`: raw GraphQL calls to `mobile.nectr.com.au/graphql`.
- `coordinator.py` — polls on the configured interval; backfills hourly usage into HA
  recorder statistics (once on fresh install, on demand via `nectr.backfill_history`).
- `sensor.py` entities · `config_flow.py` setup + options · `const.py` catalog and backfill
  ceilings · `__init__.py` entry setup and service registration.

## Tests

```bash
( rc=0; for f in tests/*.py; do echo "== $f"; python3 "$f" || rc=1; done; exit $rc )
```

Five standalone scripts, no install step — they stub `homeassistant` rather than import it.
Cover: backfill limits and service wiring, generic-sensor device_class, hourly-injection
date ranges, interval-selector typing, sensor default buckets. Runs all five, prints each
filename, exits non-zero if any failed.

Use that exact form. `|| break` looks equivalent and is not: `break` returns 0, so the loop
exits 0 and a failing suite reports success.

**pytest collects nothing here.** Test functions are named `demo()`, not `test_*`, so
`pytest tests/` passes having run zero tests. Never take that as green.

`coordinator.py` also has a `_demo()` self-test (`python3 coordinator.py`), but it imports
`aiohttp` and `homeassistant` at module level, so it runs only inside an HA environment.

## Deploy

Nothing is automated — no CI, no `.github/`, no deploy on push to `master`.

To release: bump `version` in `manifest.json` and add a `CHANGELOG.md` entry (one commit),
tag `vX.Y.Z`, create the GitHub release. HACS reads GitHub releases, so an untagged push
reaches nobody. Verify by updating in HACS, restarting HA, then checking the Nectr entities
under Settings → Devices & Services and the log for `custom_components.nectr`.

## Non-negotiables

These look like bugs or cleanup targets and are not.

- The flat root layout is load-bearing. `hacs.json` sets `"content_in_root": true`; moving
  files under `custom_components/nectr/` to match the usual convention, without changing
  that flag, breaks HACS installs for every existing user.
- `GRANUALRITY` in `api.py`'s `getUsageInfo` query is the vendor's own misspelled GraphQL
  type name (corroborated in the captured traffic log). Correcting it invalidates the query.
- Usage dates are `DD/MM/YYYY`, `toDate` exclusive (the day after `fromDate`) —
  `coordinator.py`. Verified against real portal traffic in #18; ISO dates with
  `fromDate == toDate` was the earlier guess and was wrong on both counts.
- `STATE_TIMEZONES` (`coordinator.py`) is keyed by full state name: `getUserBrief` returns
  `"QUEENSLAND"`, not `"QLD"`. An abbreviation-keyed map silently fell back to Brisbane (#18).
- `_async_clear_statistics` (`coordinator.py`) must use `Recorder.async_clear_statistics()`.
  `statistics.clear_statistics()` asserts it is on the recorder's own thread, which
  `async_add_executor_job` is not (#41).
- `async_backfill_history` clears statistics before re-importing (`coordinator.py`): HA
  statistics need a monotonic cumulative `sum`, and an earlier window restarting from 0
  would create a discontinuity.
- `MAX_BACKFILL_DAYS` (1095, `const.py`) and `_missing_dates(max_days=30)` (`coordinator.py`)
  are deliberate ceilings, so a typo or a long outage can't fan out into thousands of
  sequential API calls.
- Every `SelectSelector` default must be `str()`-wrapped (`config_flow.py`): HA validates it
  against `vol.Schema(str)`, and the raw int is the "expected str" bug.
- `NectrGenericSensor` always sets `self._attr_device_class`, even to `None` (`sensor.py`).
  HA's `Entity._attr_device_class` is a bare annotation with no class-level default, so
  leaving it unset raises `AttributeError` on read (#30).
- `coordinator.py::_demo()` is a test, not dead code — the one exception to the
  no-dead-code rule.
- `api.py`'s `App-Version: 2.9.0` header mimics the mobile app. Whether the server enforces
  it is unverified; don't drop it without testing against the live API.

## Don'ts

- Don't hardcode credentials — email/password come from the config entry (`entry.data`),
  never from source.
- Don't commit or paste `nectr_graphql_logs.jsonl`: a gitignored local traffic capture
  containing auth material.
