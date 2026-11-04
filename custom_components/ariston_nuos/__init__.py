"""Ariston Nuos heat pump water heaters (Ariston NET cloud)."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AristonNuosApi
from .const import CONF_GATEWAY, CONF_MODEL
from .coordinator import AristonNuosCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.WATER_HEATER,
]

type AristonNuosConfigEntry = ConfigEntry[AristonNuosCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AristonNuosConfigEntry) -> bool:
    """Set up one water heater."""
    api = AristonNuosApi(
        async_get_clientsession(hass), entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    )
    coordinator = AristonNuosCoordinator(
        hass,
        entry,
        api,
        entry.data[CONF_GATEWAY],
        entry.title,
        entry.data.get(CONF_MODEL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: AristonNuosConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: AristonNuosConfigEntry) -> bool:
    """Unload."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
    return unloaded
