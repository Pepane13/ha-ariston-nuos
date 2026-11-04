"""Select: operative mode (same as the water heater operation, handy on dashboards)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import MODES
from .entity import AristonNuosEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([NuosModeSelect(entry.runtime_data)])


class NuosModeSelect(AristonNuosEntity, SelectEntity):
    _attr_translation_key = "mode"
    _attr_options = [m.lower() for m in MODES]

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "mode_select")

    @property
    def current_option(self) -> str | None:
        mode = self.coordinator.mode
        return mode.lower() if mode else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_mode(option.upper())
