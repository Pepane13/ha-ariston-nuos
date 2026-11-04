"""Integration tests in a Home Assistant core, against a mocked Ariston cloud."""

import json

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

from custom_components.ariston_nuos.const import API_URL, DOMAIN, PLANT

GW = "TESTGW000001"
LIVE = {
    "on": True,
    "opMode": 1,
    "waterTemp": 51.6,
    "comfortTemp": 45,
    "reducedTemp": 40,
    "procReqTemp": 45,
    "boostOn": False,
    "hpState": 1,
}
SETTINGS = {
    "SlpMaxSetpointTemperature": 70,
    "SlpMinSetpointTemperature": 40,
    "SlpMaxGreenTemperature": 53,
    "SlpAntilegionellaOnOff": 1.0,
    "SlpPreHeatingOnOff": False,
    "SlpHeatingRate": 2,
}
CONS = [{"k": 8, "p": 1, "v": [0.2, 0.25]}, {"k": 9, "p": 1, "v": [0, 2.5]}]


def _cloud(aioclient_mock, live=None):
    aioclient_mock.post(f"{API_URL}accounts/login", json={"token": "t"})
    aioclient_mock.get(
        f"{API_URL}velis/plants",
        json=[{"gw": GW, "name": "Cumulus", "wheType": 4, "wheModelType": 5}],
    )
    aioclient_mock.get(f"{API_URL}velis/{PLANT}/{GW}", json=live or LIVE)
    aioclient_mock.get(f"{API_URL}velis/{PLANT}/{GW}/plantSettings", json=SETTINGS)
    aioclient_mock.get(
        f"{API_URL}remote/reports/{GW}/consSequencesApi8?usages=DhwHeatingPumpElec%2CDhwResistorElec",
        json=CONS,
    )
    for path in ("operativeMode", "temperatures", "boost", "switch", "plantSettings"):
        aioclient_mock.post(f"{API_URL}velis/{PLANT}/{GW}/{path}", text="")


def _posts(aioclient_mock, path):
    return [
        json.loads(data) if isinstance(data, (str, bytes)) else data
        for method, url, data, _ in aioclient_mock.mock_calls
        if method == "POST" and str(url).endswith(path)
    ]


async def _setup(hass, aioclient_mock):
    _cloud(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Cumulus",
        unique_id=GW,
        data={"username": "u@example.com", "password": "p", "gateway": GW, "model": 5},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _eid(hass, domain, key):
    from homeassistant.helpers import entity_registry as er

    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{GW}-{key}")


async def test_entities(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    wh = hass.states.get(_eid(hass, "water_heater", "water_heater"))
    assert wh.state == "COMFORT"
    assert wh.attributes["current_temperature"] == 51.6
    assert wh.attributes["temperature"] == 45
    assert wh.attributes["min_temp"] == 40 and wh.attributes["max_temp"] == 70
    assert wh.attributes["operation_list"] == ["GREEN", "COMFORT", "FAST", "IMEMORY"]
    assert hass.states.get(_eid(hass, "binary_sensor", "heat_pump")).state == "on"
    assert hass.states.get(_eid(hass, "switch", "boost")).state == "off"
    assert hass.states.get(_eid(hass, "switch", "anti_legionella")).state == "on"
    assert hass.states.get(_eid(hass, "number", "max_green_temperature")).state == "53.0"
    assert hass.states.get(_eid(hass, "sensor", "heat_pump_energy_last_day")).state == "0.45"
    assert hass.states.get(_eid(hass, "sensor", "resistor_energy_last_day")).state == "2.5"
    assert hass.states.get(_eid(hass, "select", "mode_select")).state == "comfort"
    hp = hass.states.get(_eid(hass, "sensor", "heat_pump_energy"))
    assert hp.state == "0.25" and hp.attributes["state_class"] == "total"
    assert hass.states.get(_eid(hass, "sensor", "resistor_energy")).state == "2.5"
    assert hass.states.get(_eid(hass, "sensor", "requested_temperature")).attributes["state_class"] == "measurement"


async def test_green_sends_old_mode(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    wh = _eid(hass, "water_heater", "water_heater")
    await hass.services.async_call(
        "water_heater", "set_operation_mode", {"entity_id": wh, "operation_mode": "GREEN"}, blocking=True
    )
    assert _posts(aioclient_mock, "/operativeMode") == [{"new": 0, "old": 1}]
    assert hass.states.get(wh).state == "GREEN"  # shown at once, verified 20 s later


async def test_same_mode_not_sent(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    wh = _eid(hass, "water_heater", "water_heater")
    await hass.services.async_call(
        "water_heater", "set_operation_mode", {"entity_id": wh, "operation_mode": "COMFORT"}, blocking=True
    )
    assert _posts(aioclient_mock, "/operativeMode") == []


async def test_set_temperature_with_mode(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    wh = _eid(hass, "water_heater", "water_heater")
    await hass.services.async_call(
        "water_heater",
        "set_temperature",
        {"entity_id": wh, "temperature": 52, "operation_mode": "GREEN"},
        blocking=True,
    )
    assert _posts(aioclient_mock, "/operativeMode") == [{"new": 0, "old": 1}]
    assert _posts(aioclient_mock, "/temperatures") == [
        {"new": {"comfort": 52.0, "reduced": 40}, "old": {"comfort": 45, "reduced": 40}}
    ]
    assert hass.states.get(wh).attributes["temperature"] == 52


async def test_boost_and_settings(hass: HomeAssistant, aioclient_mock):
    await _setup(hass, aioclient_mock)
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": _eid(hass, "switch", "boost")}, blocking=True
    )
    assert _posts(aioclient_mock, "/boost") == [True]
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": _eid(hass, "switch", "anti_legionella")}, blocking=True
    )
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": _eid(hass, "number", "max_green_temperature"), "value": 55},
        blocking=True,
    )
    assert _posts(aioclient_mock, "/plantSettings") == [
        {"SlpAntilegionellaOnOff": {"new": 0.0, "old": 1.0}},
        {"SlpMaxGreenTemperature": {"new": 55, "old": 53}},
    ]


async def test_config_flow(hass: HomeAssistant, aioclient_mock):
    _cloud(aioclient_mock)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "u@example.com", "password": "p"}
    )
    assert result["type"] == "create_entry"
    assert result["title"] == "Cumulus"
    assert result["data"]["gateway"] == GW
    assert result["result"].unique_id == GW


async def test_config_flow_bad_login(hass: HomeAssistant, aioclient_mock):
    aioclient_mock.post(f"{API_URL}accounts/login", status=401)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "u@example.com", "password": "bad"}
    )
    assert result["errors"] == {"base": "invalid_auth"}
