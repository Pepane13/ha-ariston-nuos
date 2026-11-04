"""Test fixtures: load the integration from this repository."""

from pathlib import Path

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def _custom(enable_custom_integrations):
    import custom_components

    repo = str(Path(__file__).resolve().parents[1] / "custom_components")
    if repo not in list(custom_components.__path__):
        custom_components.__path__.append(repo)
    yield
