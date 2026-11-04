"""Switches: power, boost, anti-legionella, preheating."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AristonNuosConfigEntry
from .const import D_BOOST_ON, D_ON, S_ANTILEGIONELLA, S_PREHEATING
from .coordinator import AristonNuosCoordinator
from .entity import AristonNuosEntity


@dataclass(frozen=True, kw_only=True)
class NuosSwitchDescription(SwitchEntityDescription):
    """Where the value lives and how to change it."""

    value: Callable[[AristonNuosCoordinator], Any]
    setter: Callable[[AristonNuosCoordinator, bool], Awaitable[None]]


def _numeric_setting(key: str) -> dict:
    """Setting stored as 1.0 / 0.0 (anti-legionella), old value sent in the same form."""
    return dict(
        value=lambda c: c.settings.get(key),
        setter=lambda c, on: c.async_set_setting(
            key, 1.0 if on else 0.0, old=1.0 if c.settings.get(key) else 0.0
        ),
    )


def _bool_setting(key: str) -> dict:
    """Setting stored as a boolean (preheating)."""
    return dict(
        value=lambda c: c.settings.get(key),
        setter=lambda c, on: c.async_set_setting(key, bool(on)),
    )


SWITCHES: tuple[NuosSwitchDescription, ...] = (
    NuosSwitchDescription(
        key="power",
        translation_key="power",
        value=lambda c: c.live.get(D_ON),
        setter=lambda c, on: c.async_set_power(on),
    ),
    NuosSwitchDescription(
        key="boost",
        translation_key="boost",
        value=lambda c: c.live.get(D_BOOST_ON),
        setter=lambda c, on: c.async_set_boost(on),
    ),
    NuosSwitchDescription(
        key="anti_legionella",
        translation_key="anti_legionella",
        entity_category=EntityCategory.CONFIG,
        **_numeric_setting(S_ANTILEGIONELLA),
    ),
    NuosSwitchDescription(
        key="preheating",
        translation_key="preheating",
        entity_category=EntityCategory.CONFIG,
        **_bool_setting(S_PREHEATING),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AristonNuosConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(NuosSwitch(coordinator, d) for d in SWITCHES)


class NuosSwitch(AristonNuosEntity, SwitchEntity):
    entity_description: NuosSwitchDescription

    def __init__(self, coordinator: AristonNuosCoordinator, description: NuosSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        return super().available and self.entity_description.value(self.coordinator) is not None

    @property
    def is_on(self) -> bool | None:
        value = self.entity_description.value(self.coordinator)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.setter(self.coordinator, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.setter(self.coordinator, False)
