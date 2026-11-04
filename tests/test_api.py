"""Pure tests of the request bodies (no Home Assistant needed)."""

import pytest

from custom_components.ariston_nuos.api import last_day_energy, mode_change_body


def test_green_carries_old_mode():
    # the bug of python-ariston-api 0.19.9: {"new": 0} alone is ignored by the cloud
    assert mode_change_body("GREEN", 1) == {"new": 0, "old": 1}


def test_unknown_old_never_equals_new():
    assert mode_change_body("GREEN", None) == {"new": 0, "old": 1}
    assert mode_change_body("COMFORT", None) == {"new": 1, "old": 0}
    assert mode_change_body("IMEMORY", 3) == {"new": 3, "old": 0}


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        mode_change_body("ECO", 1)


def test_last_day_energy():
    seq = [
        {"k": 8, "p": 1, "v": [0.1, 0.2, "x", None, 0.25]},
        {"k": 9, "p": 1, "v": [1, 1.5]},
        {"k": 8, "p": 2, "v": [99]},
    ]
    assert last_day_energy(seq, 8) == 0.55
    assert last_day_energy(seq, 9) == 2.5
    assert last_day_energy(seq, 7) is None
    assert last_day_energy(None, 8) is None
