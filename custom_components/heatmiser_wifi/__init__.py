"""Heatmiser Wifi Platform for Home Assistant."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.discovery import load_platform
from heatmiser_wifi import Heatmiser
from homeassistant.components.climate import (ClimateEntity)

from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_PIN, ATTR_FRIENDLY_NAME )

import logging
_LOGGER = logging.getLogger(__name__)

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .schedule import validate_schedule
from homeassistant.exceptions import HomeAssistantError

DOMAIN = 'heatmiser_wifi'

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_HOST): cv.string,
                vol.Optional(CONF_PORT, default=8068): cv.port,
                vol.Optional(CONF_PIN, default=0): cv.positive_int,
                vol.Optional(ATTR_FRIENDLY_NAME, default='_not_set_'): cv.string,
                vol.Optional('max_temp', default=25): cv.positive_int,
                vol.Optional('min_temp', default=5): cv.positive_int,
                vol.Optional('step_temp', default=1): cv.positive_int,
                vol.Optional('enable_experimental_hold', default=False): cv.boolean
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Keep device setup in its worker thread; register the UI on the event loop."""
    if not await hass.async_add_executor_job(setup, hass, config):
        return False
    try:
        from .frontend_setup import async_register_frontend

        await async_register_frontend(hass)
    except Exception:  # A dashboard failure must not disable working heating.
        _LOGGER.exception("Schedule card could not be registered; heating remains available")
    return True


def setup(hass: HomeAssistant, config: ConfigType) -> bool:

    heatmiser = Heatmiser(config[DOMAIN].get(CONF_HOST),config[DOMAIN].get(CONF_PORT),config[DOMAIN].get(CONF_PIN))

    heatmiser.connect()

    hass.data[DOMAIN] = {
        'name': config[DOMAIN].get(ATTR_FRIENDLY_NAME),
        'max_temp': config[DOMAIN].get('max_temp'),
        'min_temp': config[DOMAIN].get('min_temp'),
        'temp_step': config[DOMAIN].get('step_temp'),
        'time_offset': 0,
        'heatmiser' : heatmiser,
        'heatmiser_info': heatmiser.get_info()
    }

    heatmiser.disconnect()

    load_platform(hass, 'climate', DOMAIN, {}, config)
    load_platform(hass, 'sensor', DOMAIN, {}, config)
    load_platform(hass, 'switch', DOMAIN, {}, config)
    load_platform(hass, 'number', DOMAIN, {}, config)

    def set_value(call):
        name = call.data.get("name")
        value = call.data.get("value")

        hass.data[DOMAIN]['heatmiser'].connect()
        hass.data[DOMAIN]['heatmiser'].set_value(name,value)
        hass.data[DOMAIN]['heatmiser'].disconnect()
        hass.data[DOMAIN]['heatmiser_info'][name] = value

    def update_date_time(call):
        hass.data[DOMAIN]['heatmiser'].connect()
        hass.data[DOMAIN]['heatmiser'].set_value('date_time',hass.data[DOMAIN]['time_offset'])
        hass.data[DOMAIN]['heatmiser'].disconnect()


    def update_triggers(call):
        trigger = call.data.get("trigger")
        values = call.data.get("values")

        try:
            values = validate_schedule(trigger, values)
        except (ValueError, TypeError) as err:
            raise HomeAssistantError(str(err)) from err

        heatmiser = hass.data[DOMAIN]['heatmiser']

        try:
            heatmiser.connect()
            info = heatmiser.get_info()
            if info.get('program_mode') != '2/5 mode':
                raise HomeAssistantError("Weekday/weekend schedules require 5/2 day mode")
            if info.get('temperature_format') != 'Celsius':
                raise HomeAssistantError("Schedule editing currently requires Celsius")
            heatmiser.set_value(trigger, values)
            # Read the device back; never present the submitted draft as device state.
            hass.data[DOMAIN]['heatmiser_info'] = heatmiser.get_info()
        finally:
            heatmiser.disconnect()

    if config[DOMAIN].get("enable_experimental_hold", False):
        from .hold import execute_hold

        async def hold_action(call):
            # A separate client avoids sharing the polling socket.
            client = Heatmiser(
                config[DOMAIN].get(CONF_HOST),
                config[DOMAIN].get(CONF_PORT),
                config[DOMAIN].get(CONF_PIN),
            )
            temperature = call.data.get("temperature") if call.service == "hold_on" else None
            try:
                await hass.async_add_executor_job(
                    execute_hold, client, temperature,
                    config[DOMAIN].get("min_temp"), config[DOMAIN].get("max_temp"),
                )
            except Exception as err:
                raise HomeAssistantError(
                    "Hold action failed. Inspect the thermostat; a hold may remain active."
                ) from err

        hass.services.register(
            DOMAIN, "hold_on", hold_action,
            schema=vol.Schema({vol.Required("temperature"): vol.All(
                int, vol.Range(min=5, max=30)
            )}),
        )
        hass.services.register(DOMAIN, "hold_off", hold_action, schema=vol.Schema({}))

    hass.services.register(DOMAIN, "set_value", set_value)
    hass.services.register(DOMAIN, "update_date_time", update_date_time)
    hass.services.register(DOMAIN, "update_triggers", update_triggers)

    return True
