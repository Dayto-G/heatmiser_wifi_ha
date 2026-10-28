"""Select a simulation profile; no option enables physical control."""
from homeassistant.components.select import SelectEntity
from .reference_monitor import DATA


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    if DATA in hass.data:
        async_add_entities([ReferenceProfile(hass.data[DATA])])


class ReferenceProfile(SelectEntity):
    _attr_name = "Reference simulation profile"
    _attr_unique_id = "heatmiser_wifi_reference_profile"
    _attr_options = ["usb", "battery"]
    _attr_should_poll = False
    entity_id = "select.heatmiser_reference_profile"

    def __init__(self, monitor):
        self.monitor = monitor

    @property
    def current_option(self):
        return self.monitor.engine.profile

    async def async_select_option(self, option):
        self.monitor.engine.change_profile(option, self.hass.loop.time())
        self.monitor.update()
        self.async_write_ha_state()
