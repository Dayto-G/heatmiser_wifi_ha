"""Diagnostic entities for the read-only reference simulator."""
from homeassistant.components.sensor import SensorEntity
from .reference_monitor import DATA

FIELDS = {
    "status": ("Reference status", None),
    "temperature": ("Reference reported temperature", "°C"),
    "battery": ("Reference battery", "%"),
    "power": ("Reference power", None),
    "report_age_seconds": ("Reference report age", "s"),
    "measurement_age_seconds": ("Reference measurement age", "s"),
    "simulated_demand": ("Reference simulated demand", None),
    "remaining_demand_seconds": ("Reference demand remaining", "s"),
}


class ReferenceSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(self, monitor, key):
        self.monitor, self.key = monitor, key
        self._attr_name, self._attr_native_unit_of_measurement = FIELDS[key]
        self._attr_unique_id = f"heatmiser_wifi_reference_{key}"
        self.entity_id = f"sensor.heatmiser_reference_{key}"

    @property
    def native_value(self):
        return self.monitor.snapshot.get(self.key)

    @property
    def extra_state_attributes(self):
        return self.monitor.snapshot if self.key == "status" else None

    async def async_added_to_hass(self):
        self.monitor.listeners.append(self.async_write_ha_state)
        self.async_on_remove(lambda: self.monitor.listeners.remove(self.async_write_ha_state))


def reference_entities(hass):
    return [ReferenceSensor(hass.data[DATA], key) for key in FIELDS]
