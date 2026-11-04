"""Minimal async client for the Ariston NET cloud API, limited to Nuos heat pump water heaters.

The API is not publicly documented. Endpoints follow the reverse-engineered
python-ariston-api project, with one deliberate difference: mode changes always carry
the current mode as ``old``. The cloud answers "success" but ignores a change whose body
has no ``old`` key; a missing ``old`` most likely reads as 0, which is GREEN, so GREEN
could never be selected (python-ariston-api 0.19.9 and earlier).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import aiohttp

from .const import (
    API_URL,
    CONS_USAGES,
    MODES,
    PLANT,
    RATE_LIMIT_PAUSE,
    REQUEST_TIMEOUT,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class AristonError(Exception):
    """Error raised by the Ariston cloud."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class AristonAuthError(AristonError):
    """Login refused (wrong credentials)."""


def mode_change_body(new: str, old: int | None) -> dict[str, int]:
    """Body of an operative mode change, always with an ``old`` that differs from ``new``.

    When the current mode is unknown, an ``old`` different from ``new`` is sent
    (COMFORT for GREEN, GREEN otherwise) so that the cloud applies the change.
    """
    if new not in MODES:
        raise ValueError(f"Unknown mode {new}")
    new_value = MODES[new]
    if old is None or old == new_value:
        old = MODES["COMFORT"] if new_value == MODES["GREEN"] else MODES["GREEN"]
    return {"new": new_value, "old": int(old)}


def last_day_energy(sequences: list[dict[str, Any]] | None, kind: int) -> float | None:
    """Energy of the most recent reporting period (p = 1, hourly buckets), in kWh."""
    for seq in sequences or []:
        if isinstance(seq, dict) and seq.get("k") == kind and seq.get("p") == 1:
            values = seq.get("v")
            if not isinstance(values, list):
                return None
            total = 0.0
            for value in values:
                try:
                    total += float(value)
                except (TypeError, ValueError):
                    continue
            return round(total, 2)
    return None


def last_bucket(sequences: list[dict[str, Any]] | None, kind: int) -> float | None:
    """Most recent hourly bucket of the last-day sequence (p = 1), in kWh."""
    for seq in sequences or []:
        if isinstance(seq, dict) and seq.get("k") == kind and seq.get("p") == 1:
            values = seq.get("v")
            if not isinstance(values, list) or not values:
                return None
            try:
                return round(float(values[-1]), 3)
            except (TypeError, ValueError):
                return None
    return None


class AristonNuosApi:
    """Ariston NET client. Requests are serialised: the cloud dislikes bursts."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._token: str | None = None
        self._lock = asyncio.Lock()
        self._blocked_until = 0.0

    # ------------------------------------------------------------------ transport

    async def _raw(self, method: str, path: str, body: Any = None, auth: bool = True) -> Any:
        if time.monotonic() < self._blocked_until:
            raise AristonError("Ariston cloud rate limit: requests paused", 429)
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if auth:
            headers["ar.authToken"] = self._token or ""
        data = None if body is None else json.dumps(body)
        try:
            async with self._session.request(
                method,
                API_URL + path,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    if resp.status == 429:
                        self._blocked_until = time.monotonic() + RATE_LIMIT_PAUSE.total_seconds()
                    raise AristonError(f"HTTP {resp.status}: {text[:200]}", resp.status)
                return json.loads(text) if text else None
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise AristonError(f"Ariston cloud unreachable: {err}") from err

    async def _login(self) -> None:
        try:
            res = await self._raw(
                "POST", "accounts/login", {"usr": self._username, "pwd": self._password}, auth=False
            )
        except AristonError as err:
            if err.status in (400, 401, 403, 404, 405):
                raise AristonAuthError("Login refused", err.status) from err
            raise
        if not isinstance(res, dict) or not res.get("token"):
            raise AristonAuthError("Login failed: no token returned", 401)
        self._token = res["token"]

    async def _request(self, method: str, path: str, body: Any = None) -> Any:
        async with self._lock:
            if not self._token:
                await self._login()
            try:
                return await self._raw(method, path, body)
            except AristonError as err:
                if err.status in (401, 405):  # expired token
                    self._token = None
                    await self._login()
                    return await self._raw(method, path, body)
                if err.status == 404:
                    return None
                raise

    # ------------------------------------------------------------------ reading

    async def async_login(self) -> None:
        """Check the credentials."""
        async with self._lock:
            await self._login()

    async def async_get_plants(self) -> list[dict[str, Any]]:
        """Water heaters of the account (gw, name, wheType, wheModelType...)."""
        return await self._request("GET", "velis/plants") or []

    async def async_get_data(self, gw: str) -> dict[str, Any]:
        """Live state: on, opMode, waterTemp, comfortTemp, reducedTemp, procReqTemp, boostOn, hpState."""
        return await self._request("GET", f"velis/{PLANT}/{gw}") or {}

    async def async_get_settings(self, gw: str) -> dict[str, Any]:
        """Plant settings (min/max set points, Green maximum, anti-legionella, preheating...)."""
        return await self._request("GET", f"velis/{PLANT}/{gw}/plantSettings") or {}

    async def async_get_consumption(self, gw: str) -> list[dict[str, Any]]:
        """Consumption sequences [{k: type, p: period, v: [values]}]."""
        return (
            await self._request(
                "GET", f"remote/reports/{gw}/consSequencesApi8?usages={CONS_USAGES}"
            )
            or []
        )

    # ------------------------------------------------------------------ commands

    async def async_set_power(self, gw: str, on: bool) -> None:
        await self._request("POST", f"velis/{PLANT}/{gw}/switch", bool(on))

    async def async_set_mode(self, gw: str, mode: str, current: int | None) -> dict[str, int]:
        """Set the operative mode; ``current`` is the opMode read last (sent as ``old``)."""
        body = mode_change_body(mode, current)
        await self._request("POST", f"velis/{PLANT}/{gw}/operativeMode", body)
        return body

    async def async_set_temperatures(
        self,
        gw: str,
        comfort: float,
        reduced: float,
        old_comfort: float | None,
        old_reduced: float | None,
    ) -> None:
        await self._request(
            "POST",
            f"velis/{PLANT}/{gw}/temperatures",
            {
                "new": {"comfort": comfort, "reduced": reduced},
                "old": {"comfort": old_comfort, "reduced": old_reduced},
            },
        )

    async def async_set_boost(self, gw: str, on: bool) -> None:
        await self._request("POST", f"velis/{PLANT}/{gw}/boost", bool(on))

    async def async_set_plant_setting(self, gw: str, key: str, value: Any, old: Any) -> None:
        await self._request(
            "POST", f"velis/{PLANT}/{gw}/plantSettings", {key: {"new": value, "old": old}}
        )
