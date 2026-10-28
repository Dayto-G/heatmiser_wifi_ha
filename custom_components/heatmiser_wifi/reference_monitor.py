"""HA adapter for passive simulation. Never calls a climate/device service."""
from datetime import timedelta
import json
import logging

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval, async_track_state_change_event
from homeassistant.util import dt as dt_util

from .reference import ReferenceSimulator, number

DATA = "heatmiser_wifi_reference"
_LOGGER = logging.getLogger(__name__)


class ReferenceMonitor:
    def __init__(self, hass, config):
        self.hass, self.config = hass, config
        self.engine = ReferenceSimulator(config["mqtt_source"], config["profile"], config.get("profiles"))
        self.listeners, self.unsubscribers = [], []
        self.received_at = self.measured_at = None
        self.transport = "MQTT not connected"
        self.snapshot = {}

    async def start(self):

        @callback
        def received(message):
            try:
                payload = json.loads(message.payload)
            except (TypeError, ValueError):
                return
            before = self.engine.last_measurement
            if self.engine.ingest(payload, retained=message.retain, now=self.hass.loop.time(),
                                  epoch=dt_util.utcnow().timestamp()):
                self.received_at = dt_util.utcnow().isoformat()
                if self.engine.last_measurement != before:
                    self.measured_at = self.received_at
                self.transport = "Timestamped device notification received"
                self.update()

        try:
            topic = self.config.get("mqtt_topic", "")
            if topic and self.config.get("mqtt_source"):
                if any(char in topic for char in "+#"):
                    raise ValueError("Use one exact device events/rpc topic, no wildcards")
                from homeassistant.components import mqtt
                self.unsubscribers.append(await mqtt.async_subscribe(
                    self.hass, topic, received, qos=0))
                self.transport = "Waiting for a new device notification"
            else:
                self.transport = "HA values visible; device receipt tracking not configured"
        except Exception:
            _LOGGER.exception("Reference simulation has no MQTT subscription; internal heating unchanged")
        self.unsubscribers.append(async_track_time_interval(self.hass, self.update, timedelta(seconds=15)))
        self.unsubscribers.append(async_track_state_change_event(
            self.hass, [self.config["temperature_entity"], self.config["climate_entity"]], self.update))
        self.unsubscribers.append(self.hass.bus.async_listen_once("homeassistant_stop", self.stop))
        self.update()

    @callback
    def stop(self, _event=None):
        for unsubscribe in self.unsubscribers:
            unsubscribe()
        self.unsubscribers.clear()
        self.engine._stop(self.hass.loop.time())

    @callback
    def update(self, _event=None):
        temp = self.hass.states.get(self.config["temperature_entity"])
        climate = self.hass.states.get(self.config["climate_entity"])
        valid_temp = temp is not None and number(temp.state, 0, 40) is not None
        celsius = temp is not None and temp.attributes.get("unit_of_measurement") == "°C"
        climate_celsius = climate is not None and (
            climate.attributes.get("temperature_unit") or self.hass.config.units.temperature_unit) == "°C"
        home = climate is not None and climate.state == "heat" and climate.attributes.get("preset_mode") == "home"
        target = climate.attributes.get("temperature") if climate else None
        self.snapshot = self.engine.evaluate(now=self.hass.loop.time(), target=target,
                                            home=home and climate_celsius, available=valid_temp and celsius)
        self.snapshot.update({
            "last_device_report": self.received_at, "last_temperature_report": self.measured_at,
            "ha_entity_reported_at": temp.last_reported.isoformat() if temp else None,
            "ha_entity_temperature": number(temp.state, 0, 40) if temp else None,
            "transport": self.transport,
            "profile_settings": self.engine.profiles[self.engine.profile].__dict__,
            "minimum_on_remaining": max(0, self.engine.profiles[self.engine.profile].min_on_seconds -
                                        (self.hass.loop.time() - self.engine.started)) if self.engine.on else 0,
        })
        for listener in tuple(self.listeners):
            listener()


async def async_start_reference(hass, config, full_config):
    from homeassistant.helpers.discovery import async_load_platform

    monitor = ReferenceMonitor(hass, config)
    hass.data[DATA] = monitor
    await monitor.start()
    # Do not block integration setup while discovery loads base platforms.
    hass.async_create_task(async_load_platform(
        hass, "sensor", "heatmiser_wifi", {"reference_monitor": True}, full_config))
    hass.async_create_task(async_load_platform(hass, "select", "heatmiser_wifi", {}, full_config))
