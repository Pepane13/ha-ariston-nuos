"""Water heater entity: water temperature, comfort set point, operative mode, power."""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    ATTR_OPERATION_MODE,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import (
    D_COMFORT_TEMP,
    D_ON,
    D_WATER_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    MODES,
    S_MAX_SETPOINT,
    S_MIN_SETPOINT,
)
from .entity import AristonNuosEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([AristonNuosWaterHeater(entry.runtime_data)])


class AristonNuosWaterHeater(AristonNuosEntity, WaterHeaterEntity):
    """The water heater."""

    _attr_name = None
    _attr_translation_key = "water_heater"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_operation_list = list(MODES)
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
        | WaterHeaterEntityFeature.ON_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "water_heater")

    @property
    def current_temperature(self) -> float | None:
        value = self.coordinator.live.get(D_WATER_TEMP)
        return round(float(value), 1) if isinstance(value, (int, float)) else None

    @property
    def target_temperature(self) -> float | None:
        value = self.coordinator.live.get(D_COMFORT_TEMP)
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def min_temp(self) -> float:
        value = self.coordinator.settings.get(S_MIN_SETPOINT)
        return float(value) if isinstance(value, (int, float)) and value else DEFAULT_MIN_TEMP

    @property
    def max_temp(self) -> float:
        value = self.coordinator.settings.get(S_MAX_SETPOINT)
        return float(value) if isinstance(value, (int, float)) and value else DEFAULT_MAX_TEMP

    @property
    def current_operation(self) -> str | None:
        return self.coordinator.mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"power": self.coordinator.live.get(D_ON)}

    async def async_set_temperature(self, **kwargs: Any) -> None:
        mode = kwargs.get(ATTR_OPERATION_MODE)
        if mode:
            await self.coordinator.async_set_mode(mode)
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_set_temperature(float(temperature))

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        await self.coordinator.async_set_mode(operation_mode)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_power(False)
