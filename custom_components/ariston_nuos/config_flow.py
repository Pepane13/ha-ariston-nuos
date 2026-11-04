"""Config flow: Ariston NET account, then one entry per water heater."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AristonAuthError, AristonError, AristonNuosApi
from .const import (
    CONF_GATEWAY,
    CONF_MODEL,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CREDENTIALS = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class AristonNuosConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add an Ariston Nuos water heater."""

    VERSION = 1

    def __init__(self) -> None:
        self._username = ""
        self._password = ""
        self._plants: dict[str, dict[str, Any]] = {}

    async def _check(self, username: str, password: str) -> tuple[str | None, list]:
        api = AristonNuosApi(async_get_clientsession(self.hass), username, password)
        try:
            await api.async_login()
            plants = await api.async_get_plants()
        except AristonAuthError:
            return "invalid_auth", []
        except AristonError as err:
            _LOGGER.debug("Ariston cloud error: %s", err)
            return "cannot_connect", []
        return None, [p for p in plants if isinstance(p, dict) and p.get("gw")]

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error, plants = await self._check(
                user_input[CONF_USERNAME].strip(), user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            elif not plants:
                errors["base"] = "no_devices"
            else:
                self._username = user_input[CONF_USERNAME].strip()
                self._password = user_input[CONF_PASSWORD]
                configured = {e.unique_id for e in self._async_current_entries()}
                self._plants = {
                    p["gw"]: p for p in plants if p["gw"] not in configured
                }
                if not self._plants:
                    return self.async_abort(reason="already_configured")
                if len(self._plants) == 1:
                    return await self._async_create(next(iter(self._plants)))
                return await self.async_step_plant()
        return self.async_show_form(step_id="user", data_schema=CREDENTIALS, errors=errors)

    async def async_step_plant(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return await self._async_create(user_input[CONF_GATEWAY])
        choices = {
            gw: f"{p.get('name') or 'Ariston'} ({gw})" for gw, p in self._plants.items()
        }
        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema({vol.Required(CONF_GATEWAY): vol.In(choices)}),
        )

    async def _async_create(self, gw: str) -> ConfigFlowResult:
        plant = self._plants[gw]
        await self.async_set_unique_id(gw)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=plant.get("name") or "Ariston Nuos",
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_GATEWAY: gw,
                CONF_MODEL: plant.get("wheModelType"),
            },
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            error, _ = await self._check(
                user_input[CONF_USERNAME].strip(), user_input[CONF_PASSWORD]
            )
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: user_input[CONF_USERNAME].strip(),
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                CREDENTIALS, {CONF_USERNAME: entry.data.get(CONF_USERNAME)}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return AristonNuosOptionsFlow()


class AristonNuosOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
                    )
                }
            ),
        )
