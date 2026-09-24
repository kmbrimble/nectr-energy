"""Shared fixtures for the real-HA suite under tests/ha/.

tests/ha/ has its own pytest.ini (rootdir = tests/ha), separate from the six
tests/test_*.py scripts one level up. Those predate this suite: they're plain scripts
(run with `python tests/test_X.py`, not pytest) that stub every `homeassistant` module
by hand, some at import time. Keeping this suite's rootdir at tests/ha means an invocation
of `pytest tests/ha` never walks into tests/ and never collects them, so their sys.modules
stubs can't clobber the real `homeassistant` package in this process.
"""
import sys
from pathlib import Path

import pytest_homeassistant_custom_component.common as ha_common

pytest_plugins = ("pytest_homeassistant_custom_component",)

ROOT = Path(__file__).resolve().parent.parent.parent

# hacs.json declares content_in_root: true, so the integration lives at the repo root,
# not under custom_components/nectr — don't restructure the repo to fit HA's importer.
# Instead, symlink it into the plugin's own default test config dir (inside .venv, so
# gitignored) under custom_components/nectr, which is exactly where the `hass` fixture's
# config_dir already points and what `enable_custom_integrations` scans at runtime.
_TESTING_CONFIG_DIR = Path(ha_common.get_test_config_dir())
_NECTR_LINK = _TESTING_CONFIG_DIR / "custom_components" / "nectr"
if not _NECTR_LINK.exists():
    _NECTR_LINK.symlink_to(ROOT, target_is_directory=True)

# HA's own loader only ever puts config_dir on sys.path for the scoped duration of its
# executor-job import (see loader.py's _get_custom_components), so it's not there yet when
# pytest imports our test modules at collection time. Add it permanently for this process so
# `from custom_components.nectr... import ...` works the same at collection time and at runtime.
if str(_TESTING_CONFIG_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTING_CONFIG_DIR))
