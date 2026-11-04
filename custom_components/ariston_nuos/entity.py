"""Base entity."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AristonNuosCoordinator


class AristonNuosEntity(CoordinatorEntity[AristonNuosCoordinator]):
    """Entity of one water heater."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AristonNuosCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.gw}-{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.gw)},
            manufacturer=MANUFACTURER,
            model=f"Nuos ({coordinator.model})" if coordinator.model else "Nuos",
            name=coordinator.heater_name,
        )
