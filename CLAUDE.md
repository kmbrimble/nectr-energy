# Project Instructions

Home Assistant custom integration (domain: `nectr`) for the Nectr Energy GraphQL API.
Flat file layout at repo root (not nested under `custom_components/`) — this *is* the
component directory. Code style lives in `.claude/rules/code-quality.md`.

## Architecture

- `api.py` — `NectrApiClient`: raw GraphQL calls to `mobile.nectr.com.au/graphql`.
- `coordinator.py` — polls the API on the configured interval, backfills hourly usage
  into HA's recorder statistics.
- `sensor.py` — entities built from coordinator data.

## Don'ts

- Don't hardcode credentials — email/password come from the config flow entry, never
  from source.

## Testing

Two separate suites — do not mix them in one pytest invocation:

- **Stub tests** (`tests/test_*.py`, six files): plain scripts that hand-stub every
  `homeassistant` module, some at import time. Run each with the system `python3`, no venv or
  install needed: `for f in tests/test_*.py; do python3 "$f"; done`. Not pytest-collectible
  from `tests/ha` (see below), but if you ever run bare `pytest tests` from the repo root it
  hard-errors immediately (a `pytest_plugins`-in-non-top-level-conftest error) rather than
  silently mixing the two suites' `sys.modules` stubs.
- **Real-HA suite** (`tests/ha/`): runs against the actual `homeassistant` package via
  `pytest-homeassistant-custom-component`. Setup:
  - `uv venv --python 3.14 .venv` (gitignored), then
    `uv pip install --python .venv/bin/python -r requirements_test.txt`.
  - `requirements_test.txt` pins `pytest-homeassistant-custom-component==0.13.365`, which pulls
    in **homeassistant 2026.9.2** (live is 2026.9.1 — one patch version apart) plus recorder's
    own deps (SQLAlchemy etc.) transitively; nothing else needed pinning.
  - Run with: **`.venv/bin/pytest tests/ha`** (the explicit path matters — it's what makes
    pytest find `tests/ha/pytest.ini`, whose directory becomes pytest's rootdir).
  - `tests/ha/pytest.ini` sets `asyncio_mode = auto`.
    `tests/ha/pytest.ini` (not a repo-root `pytest.ini`) is deliberate: this repo's own
    `__init__.py` lives at repo root (flat/`content_in_root` layout), and if repo root is also
    pytest's rootdir, pytest tries to import that `__init__.py` as a bare top-level module
    during test-item setup and fails on its relative imports. Rooting the real-HA suite one
    level down avoids that collision entirely.
  - Import approach: `tests/ha/conftest.py` symlinks the repo root into
    `pytest_homeassistant_custom_component`'s own default test config dir, as
    `custom_components/nectr` (that's exactly the directory the `hass` fixture's
    `config_dir` already points at, and what `enable_custom_integrations` scans), and adds
    that config dir to `sys.path` so `from custom_components.nectr... import ...` also works
    at module-import time in test files (HA's own loader only puts it on `sys.path` for the
    scoped duration of its own executor-job import). Both live under `.venv/`, so gitignored,
    nothing written outside it.
  - Fixture order matters: always list `recorder_mock` **before** `hass` in a test's
    signature (`async def test_x(recorder_mock, hass, ...)`) — the other order trips an
    internal assertion in the plugin's `recorder_db_url` fixture.
  - Any test that touches `hass.config_entries.flow`/`async_setup` needs `recorder_mock` even
    if it doesn't call statistics APIs itself — `manifest.json` declares `recorder` as a
    dependency, so HA sets it up as a side effect of loading the `nectr` integration at all.

### Known gaps surfaced by the real-HA suite (not fixed here — see CHANGELOG)

- `config_flow.py`'s `async_step_user` wraps `async_set_unique_id` /
  `_abort_if_unique_id_configured` in a bare `except Exception:`, which also swallows the
  `AbortFlow` control-flow exception those raise. A genuine duplicate-account submission
  surfaces as a generic `auth_error` form instead of an abort. Guarded by
  `tests/ha/test_config_flow.py::test_duplicate_email_is_aborted`, marked
  `xfail(strict=True)` until fixed.
