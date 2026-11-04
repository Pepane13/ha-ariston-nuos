"""Sensors: water temperature, set points, mode, last-day energy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import D_PROC_REQ_TEMP, D_WATER_TEMP, MODES
from .coordinator import AristonNuosCoordinator
from .entity import AristonNuosEntity


@dataclass(frozen=True, kw_only=True)
class NuosSensorDescription(SensorEntityDescription):
    value: Callable[[AristonNuosCoordinator], Any]
    last_reset: Callable[[AristonNuosCoordinator], Any] | None = None


def _num(v: Any) -> float | None:
    return round(float(v), 2) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


SENSORS: tuple[NuosSensorDescription, ...] = (
    NuosSensorDescription(
        key="water_temperature",
        translation_key="water_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value=lambda c: _num(c.live.get(D_WATER_TEMP)),
    ),
    NuosSensorDescription(
        key="requested_temperature",
        translation_key="requested_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value=lambda c: _num(c.live.get(D_PROC_REQ_TEMP)),
    ),
    NuosSensorDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=[m.lower() for m in MODES],
        value=lambda c: c.mode.lower() if c.mode else None,
    ),
    NuosSensorDescription(
        key="heat_pump_energy",
        translation_key="heat_pump_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c: _num(c.energy.get("heat_pump_hour")),
        last_reset=lambda c: c.energy.get("hour_start"),
    ),
    NuosSensorDescription(
        key="resistor_energy",
        translation_key="resistor_energy",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c: _num(c.energy.get("resistor_hour")),
        last_reset=lambda c: c.energy.get("hour_start"),
    ),
    NuosSensorDescription(
        key="heat_pump_energy_last_day",
        translation_key="heat_pump_energy_last_day",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c: _num(c.energy.get("heat_pump")),
    ),
    NuosSensorDescription(
        key="resistor_energy_last_day",
        translation_key="resistor_energy_last_day",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value=lambda c: _num(c.energy.get("resistor")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NuosSensor(coordinator, d) for d in SENSORS)


class NuosSensor(AristonNuosEntity, SensorEntity):
    entity_description: NuosSensorDescription

    def __init__(self, coordinator: AristonNuosCoordinator, description: NuosSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value(self.coordinator)

    @property
    def last_reset(self):
        if self.entity_description.last_reset is None:
            return None
        return self.entity_description.last_reset(self.coordinator)
