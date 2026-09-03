"""Guards against the "expected str" bug: HA's SelectSelector validates its
default against vol.Schema(str) internally, so any default fed to it must
already be a string, not the raw int."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from const import DEFAULT_INTERVAL, INTERVAL_OPTIONS


def test_demo():
    assert isinstance(str(DEFAULT_INTERVAL), str)
    assert str(DEFAULT_INTERVAL) in [str(v) for v in INTERVAL_OPTIONS]
    assert not isinstance(DEFAULT_INTERVAL, str)  # the raw int is what broke the selector
    print("ok")


if __name__ == "__main__":
    test_demo()
