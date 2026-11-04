"""Numbers: reduced temperature, Green maximum, set point limits, heating rate."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import (
    D_REDUCED_TEMP,
    S_HEATING_RATE,
    S_MAX_GREEN,
    S_MAX_SETPOINT,
    S_MIN_SETPOINT,
)
from .coordinator import AristonNuosCoordinator
from .entity import AristonNuosEntity


@dataclass(frozen=True, kw_only=True)
class NuosNumberDescription(NumberEntityDescription):
    value: Callable[[AristonNuosCoordinator], Any]
    setter: Callable[[AristonNuosCoordinator, float], Awaitable[None]]


def _setting(key: str) -> dict:
    return dict(
        value=lambda c: c.settings.get(key),
        setter=lambda c, v: c.async_set_setting(key, v),
    )


_TEMP = dict(
    device_class=NumberDeviceClass.TEMPERATURE,
    native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    native_step=1,
    mode=NumberMode.BOX,
)

NUMBERS: tuple[NuosNumberDescription, ...] = (
    NuosNumberDescription(
        key="reduced_temperature",
        translation_key="reduced_temperature",
        native_min_value=0,
        native_max_value=75,
        value=lambda c: c.live.get(D_REDUCED_TEMP),
        setter=lambda c, v: c.async_set_reduced_temperature(v),
        **_TEMP,
    ),
    NuosNumberDescription(
        key="max_green_temperature",
        translation_key="max_green_temperature",
        entity_category=EntityCategory.CONFIG,
        native_min_value=40,
        native_max_value=75,
        **_TEMP,
        **_setting(S_MAX_GREEN),
    ),
    NuosNumberDescription(
        key="max_setpoint_temperature",
        translation_key="max_setpoint_temperature",
        entity_category=EntityCategory.CONFIG,
        native_min_value=40,
        native_max_value=75,
        **_TEMP,
        **_setting(S_MAX_SETPOINT),
    ),
    NuosNumberDescription(
        key="min_setpoint_temperature",
        translation_key="min_setpoint_temperature",
        entity_category=EntityCategory.CONFIG,
        native_min_value=20,
        native_max_value=60,
        **_TEMP,
        **_setting(S_MIN_SETPOINT),
    ),
    NuosNumberDescription(
        key="heating_rate",
        translation_key="heating_rate",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        mode=NumberMode.BOX,
        **_setting(S_HEATING_RATE),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NuosNumber(coordinator, d) for d in NUMBERS)


class NuosNumber(AristonNuosEntity, NumberEntity):
    entity_description: NuosNumberDescription

    def __init__(self, coordinator: AristonNuosCoordinator, description: NuosNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and isinstance(
            self.entity_description.value(self.coordinator), (int, float)
        )

    @property
    def native_value(self) -> float | None:
        value = self.entity_description.value(self.coordinator)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        if float(value).is_integer():
            value = int(value)
        await self.entity_description.setter(self.coordinator, value)
