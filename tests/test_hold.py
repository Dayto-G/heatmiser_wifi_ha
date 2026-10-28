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
        self.pin = 1234
        self.sock = self
        self.crc16 = self
        self.pending = None
        self.frames = []
        self.received = 0
        self.fail_response = False
    def CRC16(self, frame):
        self.crc_input = bytes(frame)
        return (0xAA, 0xBB)
    def sendall(self, frame):
        self.assert_no_pending()
        self.frames.append(bytes(frame))
        assert int.from_bytes(frame[1:3], "little") == len(frame)
        assert frame[:1] == bytes([0xA3]) and frame[3:5] == self.pin.to_bytes(2, "little")
        assert frame[-2:] == bytes([0xAA, 0xBB]) and self.crc_input == bytes(frame[:-2])
        index = 6
        for _ in range(frame[5]):
            address = int.from_bytes(frame[index:index+2], "little")
            size = frame[index+2]
            data = bytes(frame[index+3:index+3+size])
            self.events.append((address, data))
            if address == 32 and not self.ignore_timer:
                self.timer = self.round_timer if self.round_timer is not None else int.from_bytes(data, "little")
            if address == 18 and not self.fail_target:
                self.info["set_room_temp"] = data[0]
            index += 3 + size
        assert index == len(frame) - 2
        self.pending = self.raw()
    def assert_no_pending(self):
        assert self.pending is None, "Previous write acknowledgement left unread"
    def _receive_dcb(self):
        self.received += 1
        if self.fail_response: raise OSError("response lost")
        raw, self.pending = self.pending, None
        return 0, raw
    def raw(self):
        raw = bytearray(43)
        raw[4] = 2
        raw[18] = self.info["set_room_temp"]
        raw[31:33] = self.timer.to_bytes(2, "little")
        return raw
    def connect(self): self.events.append("connect")
    def disconnect(self): self.events.append("disconnect")
    def get_info(self):
        self.assert_no_pending()
        return dict(self.info)
    def get_dcb(self):
        self.assert_no_pending()
        return self.raw()
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
        self.assertLess(c.events.index((32, b"\x1e\x00")), c.events.index((18, b"\x13")))
        self.assertEqual(c.info["set_room_temp"], 19)
        self.assertEqual([f[5] for f in c.frames], [1, 2])
        self.assertEqual(c.received, 2)
        self.assertIsNone(c.pending)
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
        with self.assertRaisesRegex(ValueError, "received 18 C/30 min"): hold.execute_hold(c, 19)
        self.assertEqual(c.timer, 30)
        self.assertEqual(c.events[-1], "disconnect")
    def test_lost_ack_never_sends_target_or_retries(self):
        c = Fake()
        c.fail_response = True
        with self.assertRaises(OSError): hold.execute_hold(c, 19)
        self.assertEqual(len(c.frames), 1)
        self.assertEqual(c.info["set_room_temp"], 18)
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
