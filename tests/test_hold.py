import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("hold", Path(__file__).parents[1] / "custom_components/heatmiser_wifi/hold.py")
hold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hold)

class Fake:
    def __init__(self, **changes):
        self.info = dict(model="PRT", temperature_format="Celsius", on_off="On",
                         run_mode="Heating mode (normal mode)", away_mode="Off", set_room_temp=18)
        self.info.update(changes)
        self.timer = 0
        self.events = []
        self.ignore_timer = False
        self.fail_target = False
        self.round_timer = None
    def connect(self): self.events.append("connect")
    def disconnect(self): self.events.append("disconnect")
    def get_info(self): return dict(self.info)
    def get_dcb(self):
        raw = bytearray(43)
        raw[4] = 2
        raw[31:33] = self.timer.to_bytes(2, "little")
        return raw
    def set_dcb(self, address, data):
        self.events.append((address, bytes(data)))
        if not self.ignore_timer:
            self.timer = self.round_timer if self.round_timer is not None else int.from_bytes(data, "little")
    def set_value(self, key, value):
        self.events.append((key, value))
        if self.fail_target: raise OSError("network lost")
        self.info[key] = value

class HoldTests(unittest.TestCase):
    def test_arm_before_target(self):
        c = Fake()
        hold.execute_hold(c, 19)
        self.assertLess(c.events.index((32, b"\x1e\x00")), c.events.index(("set_room_temp", 19)))
        self.assertEqual(c.timer, 30)
        self.assertEqual(c.events[-1], "disconnect")
    def test_custom_duration_and_boundaries(self):
        for duration in (1, 15, 30):
            c = Fake()
            hold.execute_hold(c, 19, duration_minutes=duration)
            self.assertEqual(c.timer, duration)
            self.assertIn((32, duration.to_bytes(2, "little")), c.events)
    def test_invalid_duration_does_not_connect(self):
        for duration in (0, -1, 31, 65536, True, 15.5, "15", None):
            c = Fake()
            with self.assertRaises(ValueError):
                hold.execute_hold(c, 19, duration_minutes=duration)
            self.assertEqual(c.events, [])
    def test_rounded_duration_rejected_before_target_write(self):
        c = Fake()
        c.round_timer = 30
        with self.assertRaises(ValueError):
            hold.execute_hold(c, 19, duration_minutes=15)
        self.assertEqual(c.info["set_room_temp"], 18)
        self.assertFalse(any(isinstance(e, tuple) and e[0] == "set_room_temp" for e in c.events))
    def test_cancel_only_timer(self):
        c = Fake()
        c.timer = 30
        hold.execute_hold(c)
        self.assertEqual(c.timer, 0)
        self.assertEqual(c.info["set_room_temp"], 18)
        self.assertNotIn(("set_room_temp", 18), c.events)
    def test_unconfirmed_timer_never_changes_target(self):
        c = Fake()
        c.ignore_timer = True
        with self.assertRaises(ValueError): hold.execute_hold(c, 19)
        self.assertEqual(c.info["set_room_temp"], 18)
        self.assertEqual(c.events[-1], "disconnect")
    def test_connection_failure_leaves_expiring_timer(self):
        c = Fake()
        c.fail_target = True
        with self.assertRaises(OSError): hold.execute_hold(c, 19)
        self.assertEqual(c.timer, 30)
        self.assertEqual(c.events[-1], "disconnect")
    def test_existing_hold_not_extended(self):
        c = Fake()
        c.timer = 5
        with self.assertRaises(ValueError): hold.execute_hold(c, 19)
        self.assertEqual(c.timer, 5)
    def test_reject_modes_and_models_without_writes(self):
        for options in [dict(model="DT"), dict(away_mode="On"),
                        dict(on_off="Off"), dict(run_mode="Frost protection mode"),
                        dict(temperature_format="Fahrenheit")]:
            c = Fake(**options)
            with self.assertRaises(ValueError): hold.execute_hold(c, 19)
            self.assertEqual(c.events, ["connect", "disconnect"])
    def test_validate_before_connect(self):
        for value in [True, 19.5, "19", 4, 26]:
            c = Fake()
            with self.assertRaises(ValueError): hold.execute_hold(c, value)
            self.assertEqual(c.events, [])
    def test_raw_timer_little_endian(self):
        c = Fake()
        c.timer = 258
        self.assertEqual(hold.read_hold(c), 258)

if __name__ == "__main__": unittest.main()
