"""Binary sensor: heat pump running."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import D_HP_STATE
from .entity import AristonNuosEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([NuosHeatPump(entry.runtime_data)])


class NuosHeatPump(AristonNuosEntity, BinarySensorEntity):
    _attr_translation_key = "heat_pump"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "heat_pump")

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.live.get(D_HP_STATE)
        return None if value is None else bool(value)
