"""Constants for the Ariston Nuos integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "ariston_nuos"
MANUFACTURER: Final = "Ariston"

API_URL: Final = "https://www.ariston-net.remotethermo.com/api/v2/"
USER_AGENT: Final = "RestSharp/106.11.7.0"
PLANT: Final = "slpPlantData"  # Nuos heat pump water heaters are "Velis" SLP plants
NUOS_WHE_TYPE: Final = 4  # python-ariston-api WheType.NuosSplit

CONF_GATEWAY: Final = "gateway"
CONF_MODEL: Final = "model"
CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = 2  # minutes
MIN_SCAN_INTERVAL: Final = 1
MAX_SCAN_INTERVAL: Final = 30

SETTINGS_REFRESH: Final = timedelta(hours=6)
ENERGY_REFRESH: Final = timedelta(hours=1)
VERIFY_DELAY: Final = 20  # seconds: the cloud applies a command after a few seconds
RATE_LIMIT_PAUSE: Final = timedelta(minutes=15)  # after HTTP 429
REQUEST_TIMEOUT: Final = 30  # seconds

# Operative modes (opMode). Names match the Home Assistant core "ariston" integration,
# so automations written for it keep working.
MODES: Final[dict[str, int]] = {"GREEN": 0, "COMFORT": 1, "FAST": 2, "IMEMORY": 3}
MODE_NAMES: Final[dict[int, str]] = {v: k for k, v in MODES.items()}

# Live data keys (GET velis/slpPlantData/<gw>)
D_ON: Final = "on"
D_OP_MODE: Final = "opMode"
D_WATER_TEMP: Final = "waterTemp"
D_COMFORT_TEMP: Final = "comfortTemp"
D_REDUCED_TEMP: Final = "reducedTemp"
D_PROC_REQ_TEMP: Final = "procReqTemp"
D_BOOST_ON: Final = "boostOn"
D_HP_STATE: Final = "hpState"

# Plant settings keys (GET velis/slpPlantData/<gw>/plantSettings)
S_MAX_SETPOINT: Final = "SlpMaxSetpointTemperature"
S_MIN_SETPOINT: Final = "SlpMinSetpointTemperature"
S_MAX_GREEN: Final = "SlpMaxGreenTemperature"
S_ANTILEGIONELLA: Final = "SlpAntilegionellaOnOff"
S_PREHEATING: Final = "SlpPreHeatingOnOff"
S_HEATING_RATE: Final = "SlpHeatingRate"

DEFAULT_MIN_TEMP: Final = 40
DEFAULT_MAX_TEMP: Final = 75

# Consumption report types (k) of consSequencesApi8, period p = 1 = last day (hourly buckets)
CONS_USAGES: Final = "DhwHeatingPumpElec%2CDhwResistorElec"
CONS_HEAT_PUMP: Final = 8
CONS_RESISTOR: Final = 9
