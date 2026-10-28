"""Exercise HA receipt wiring without a real event loop, broker or device."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from datetime import datetime, timezone

ROOT = Path(__file__).parents[1] / "custom_components/heatmiser_wifi"


def complete(coro):
    # All awaits below complete synchronously. Unexpected asynchronous I/O fails.
    try:
        coro.send(None)
    except StopIteration as result:
        return result.value
    raise AssertionError("Unexpected blocking operation in unit fixture")


class MonitorTests(TestCase):
    def setup_monitor(self, subscribe_error=False, topic="device/events/rpc"):
        epoch = datetime(2026, 10, 28, tzinfo=timezone.utc).timestamp()
        clock = {"now": 0}
        captured, services = {}, []
        package = ModuleType("test_reference_package"); package.__path__ = [str(ROOT)]
        async def subscribe(hass, actual_topic, handler, qos):
            if subscribe_error:
                raise RuntimeError("Broker unavailable")
            captured.update(topic=actual_topic, callback=handler, qos=qos)
            return lambda: captured.update(unsubscribed=True)
        modules = {
            "test_reference_package": package,
            "homeassistant": ModuleType("homeassistant"),
            "homeassistant.core": SimpleNamespace(callback=lambda fn: fn),
            "homeassistant.components": SimpleNamespace(mqtt=SimpleNamespace(async_subscribe=subscribe)),
            "homeassistant.helpers": ModuleType("homeassistant.helpers"),
            "homeassistant.helpers.event": SimpleNamespace(
                async_track_time_interval=lambda hass, fn, delta: lambda: None,
                async_track_state_change_event=lambda hass, ids, fn: lambda: None),
            "homeassistant.util": SimpleNamespace(dt=SimpleNamespace(
                utcnow=lambda: datetime.fromtimestamp(epoch + clock["now"], tz=timezone.utc))),
        }
        states = {
            "sensor.room": SimpleNamespace(state="17.3", attributes={"unit_of_measurement": "°C"},
                                           last_reported=datetime.now(timezone.utc)),
            "climate.heating": SimpleNamespace(state="heat", attributes={"temperature": 18, "preset_mode": "home"}),
        }
        hass = SimpleNamespace(loop=SimpleNamespace(time=lambda: clock["now"]),
                               states=SimpleNamespace(get=states.get),
                               bus=SimpleNamespace(async_listen_once=lambda name, fn: lambda: None),
                               config=SimpleNamespace(units=SimpleNamespace(temperature_unit="°C")),
                               services=services)
        with patch.dict(sys.modules, modules):
            spec = importlib.util.spec_from_file_location("test_reference_package.reference_monitor", ROOT / "reference_monitor.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            monitor = module.ReferenceMonitor(hass, {"temperature_entity": "sensor.room", "climate_entity": "climate.heating",
                                                    "profile": "battery", "mqtt_source": "device", "mqtt_topic": topic})
            complete(monitor.start())
        return monitor, captured, clock, epoch, states, services

    def test_subscription_updates_real_receipts_not_ha_cached_writes(self):
        m, captured, clock, epoch, states, services = self.setup_monitor()
        self.assertEqual(captured["topic"], "device/events/rpc")
        self.assertEqual(m.snapshot["status"], "uncertain")
        clock["now"] = 10
        states["sensor.room"].last_reported = datetime.now(timezone.utc)
        m.update()
        self.assertIsNone(m.snapshot["last_temperature_report"])
        captured["callback"](SimpleNamespace(retain=False, payload=json.dumps({
            "src": "device", "method": "NotifyFullStatus", "params": {"ts": epoch+10,
            "temperature:0": {"tC": 17.3}, "devicepower:0": {"battery": {"percent": 100}, "external": {"present": False}}}})))
        self.assertEqual(m.snapshot["status"], "current")
        self.assertEqual(m.snapshot["simulated_demand"], 1)
        clock["now"] = 610
        m.update()
        self.assertEqual(m.snapshot["simulated_demand"], 0)
        self.assertEqual(services, [])
        m.stop()
        self.assertTrue(captured["unsubscribed"])

    def test_no_broker_no_topic_and_wildcards_fail_closed(self):
        for fail, topic in [(True, "device/events/rpc"), (False, ""), (False, "#")]:
            with self.subTest(topic=topic, fail=fail):
                m, _, _, _, _, services = self.setup_monitor(fail, topic)
                self.assertEqual(m.snapshot["status"], "uncertain")
                self.assertEqual(m.snapshot["simulated_demand"], 0)
                self.assertEqual(services, [])

    def test_away_summer_off_and_celsius_guard(self):
        m, _, _, _, states, _ = self.setup_monitor()
        for preset in ["away", "Summer", None]:
            states["climate.heating"].attributes["preset_mode"] = preset
            m.update()
            self.assertEqual(m.snapshot["simulated_demand"], 0)
        states["climate.heating"].state = "unavailable"
        m.update()
        self.assertEqual(m.snapshot["simulated_demand"], 0)
        states["sensor.room"].attributes["unit_of_measurement"] = "°F"
        m.update()
        self.assertEqual(m.snapshot["status"], "offline")
