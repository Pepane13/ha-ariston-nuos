"""Data coordinator for one Ariston Nuos water heater."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AristonAuthError, AristonError, AristonNuosApi, last_day_energy
from .const import (
    CONF_SCAN_INTERVAL,
    CONS_HEAT_PUMP,
    CONS_RESISTOR,
    D_BOOST_ON,
    D_COMFORT_TEMP,
    D_ON,
    D_OP_MODE,
    D_REDUCED_TEMP,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENERGY_REFRESH,
    MODE_NAMES,
    MODES,
    SETTINGS_REFRESH,
    VERIFY_DELAY,
)

_LOGGER = logging.getLogger(__name__)

EVENT_COMMAND = f"{DOMAIN}_command"


class AristonNuosCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Reads one heater from the cloud and executes the commands of its entities.

    ``data`` holds three dicts: ``live`` (state), ``settings`` (plant settings) and
    ``energy`` (last-day energy of the heat pump and of the resistor, kWh).
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: AristonNuosApi,
        gw: str,
        name: str,
        model: str | None,
    ) -> None:
        minutes = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {gw}",
            update_interval=timedelta(minutes=minutes),
        )
        self.api = api
        self.gw = gw
        self.heater_name = name
        self.model = model
        self._live: dict[str, Any] = {}
        self._settings: dict[str, Any] = {}
        self._energy: dict[str, float | None] = {"heat_pump": None, "resistor": None}
        self._settings_at = None
        self._energy_at = None
        self._verify_unsub = None

    # ------------------------------------------------------------------ reading

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.utcnow()
        try:
            self._live = await self.api.async_get_data(self.gw)
            if self._settings_at is None or now - self._settings_at > SETTINGS_REFRESH:
                self._settings = await self.api.async_get_settings(self.gw)
                self._settings_at = now
            if self._energy_at is None or now - self._energy_at > ENERGY_REFRESH:
                self._energy_at = now
                try:
                    seq = await self.api.async_get_consumption(self.gw)
                    self._energy = {
                        "heat_pump": last_day_energy(seq, CONS_HEAT_PUMP),
                        "resistor": last_day_energy(seq, CONS_RESISTOR),
                    }
                except AristonError as err:
                    _LOGGER.debug("Energy report unavailable: %s", err)
        except AristonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except AristonError as err:
            raise UpdateFailed(str(err)) from err
        return self._snapshot()

    def force_full_refresh(self) -> None:
        """Read settings and energy again at the next refresh."""
        self._settings_at = None
        self._energy_at = None

    def _snapshot(self) -> dict[str, Any]:
        return {
            "live": dict(self._live),
            "settings": dict(self._settings),
            "energy": dict(self._energy),
        }

    @property
    def live(self) -> dict[str, Any]:
        return (self.data or {}).get("live", {})

    @property
    def settings(self) -> dict[str, Any]:
        return (self.data or {}).get("settings", {})

    @property
    def energy(self) -> dict[str, Any]:
        return (self.data or {}).get("energy", {})

    @property
    def mode(self) -> str | None:
        return MODE_NAMES.get(self.live.get(D_OP_MODE))

    # ------------------------------------------------------------------ commands

    def _push(self, **changes: Any) -> None:
        """Show the commanded value at once, then read the heater again shortly after."""
        self._live.update(changes)
        self.async_set_updated_data(self._snapshot())
        self._schedule_verify()

    def _schedule_verify(self) -> None:
        if self._verify_unsub:
            self._verify_unsub()

        @callback
        def _verify(_now) -> None:
            self._verify_unsub = None
            self.hass.async_create_task(self.async_request_refresh())

        self._verify_unsub = async_call_later(self.hass, VERIFY_DELAY, _verify)

    def _fire(self, command: str, **details: Any) -> None:
        self.hass.bus.async_fire(
            EVENT_COMMAND, {"gateway": self.gw, "command": command, **details}
        )

    async def _call(self, coro) -> Any:
        try:
            return await coro
        except AristonAuthError as err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(f"Ariston login refused: {err}") from err
        except AristonError as err:
            raise HomeAssistantError(f"Ariston cloud error: {err}") from err

    async def async_set_mode(self, mode: str) -> None:
        mode = mode.upper()
        if mode not in MODES:
            raise HomeAssistantError(f"Unknown mode {mode}")
        current = self._live.get(D_OP_MODE)
        if current == MODES[mode]:
            return
        body = await self._call(self.api.async_set_mode(self.gw, mode, current))
        self._fire("mode", new=mode, old=MODE_NAMES.get(body["old"]))
        self._push(**{D_OP_MODE: MODES[mode]})

    async def async_set_temperature(self, comfort: float) -> None:
        old_comfort = self._live.get(D_COMFORT_TEMP)
        reduced = self._live.get(D_REDUCED_TEMP)
        await self._call(
            self.api.async_set_temperatures(
                self.gw, comfort, reduced if reduced is not None else 0, old_comfort, reduced
            )
        )
        self._fire("temperature", new=comfort, old=old_comfort)
        self._push(**{D_COMFORT_TEMP: comfort})

    async def async_set_reduced_temperature(self, reduced: float) -> None:
        comfort = self._live.get(D_COMFORT_TEMP)
        if comfort is None:
            raise HomeAssistantError("Comfort set point unknown, try again after a refresh")
        old_reduced = self._live.get(D_REDUCED_TEMP)
        await self._call(
            self.api.async_set_temperatures(self.gw, comfort, reduced, comfort, old_reduced)
        )
        self._fire("reduced_temperature", new=reduced, old=old_reduced)
        self._push(**{D_REDUCED_TEMP: reduced})

    async def async_set_power(self, on: bool) -> None:
        await self._call(self.api.async_set_power(self.gw, on))
        self._fire("power", new=on)
        self._push(**{D_ON: on})

    async def async_set_boost(self, on: bool) -> None:
        await self._call(self.api.async_set_boost(self.gw, on))
        self._fire("boost", new=on)
        self._push(**{D_BOOST_ON: on})

    async def async_set_setting(self, key: str, value: Any, old: Any = None) -> None:
        if old is None:
            old = self._settings.get(key)
        await self._call(self.api.async_set_plant_setting(self.gw, key, value, old))
        self._settings[key] = value
        self._fire("setting", key=key, new=value, old=old)
        self.async_set_updated_data(self._snapshot())

    async def async_shutdown(self) -> None:
        if self._verify_unsub:
            self._verify_unsub()
            self._verify_unsub = None
        await super().async_shutdown()
