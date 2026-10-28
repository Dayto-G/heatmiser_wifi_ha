"""Safety scenarios use a virtual monotonic clock, never a thermostat."""
import importlib.util
from pathlib import Path
import sys
import unittest

spec = importlib.util.spec_from_file_location("reference_model", Path(__file__).parents[1] /
                                             "custom_components/heatmiser_wifi/reference.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def packet(temp=17.3, ts=1000, power=False, battery=100):
    return {"src": "test-device", "method": "NotifyFullStatus", "params": {
        "ts": ts, "temperature:0": {"tC": temp},
        "devicepower:0": {"battery": {"percent": battery}, "external": {"present": power}},
    }}


class ReferenceTests(unittest.TestCase):
    def model(self, profile="battery"):
        return mod.ReferenceSimulator("test-device", profile)

    def report(self, m, t=0, temp=17.3, **kw):
        return m.ingest(packet(temp, ts=1000+t, **kw), retained=False, now=t, epoch=1000+t)

    def evaluate(self, m, t=0, **kw):
        return m.evaluate(now=t, target=kw.get("target", 18), home=kw.get("home", True),
                          available=kw.get("available", True))

    def test_requested_17_5_to_18_without_report(self):
        m = self.model()
        self.report(m, temp=17.5)
        # The real room could reach 18; it is not an available input. Never
        # invent an interpolated measurement or assume an unchanged HA write.
        for minute in range(121):
            s = self.evaluate(m, minute*60)
            self.assertFalse(s["simulated_demand"])
            self.assertEqual(s["temperature"], 17.5)
        self.assertEqual(s["status"], "uncertain")

    def test_battery_limit_cannot_be_extended_by_new_low_measurements(self):
        m = self.model(); self.report(m)
        self.assertTrue(self.evaluate(m)["simulated_demand"])
        self.report(m, t=590)
        self.assertFalse(self.evaluate(m, 600)["simulated_demand"])
        self.assertFalse(self.evaluate(m, 1200)["simulated_demand"])
        self.report(m, t=1201)
        self.assertTrue(self.evaluate(m, 1201)["simulated_demand"])

    def test_no_new_temperature_after_low_report_times_out(self):
        m = self.model(); self.report(m)
        self.evaluate(m)
        self.assertFalse(self.evaluate(m, 600)["simulated_demand"])
        self.assertEqual(self.evaluate(m, 901)["status"], "uncertain")
        self.assertEqual(self.evaluate(m, 9000)["status"], "offline")

    def test_equal_real_report_refreshes_but_humidity_only_does_not(self):
        m = self.model(); self.report(m)
        self.report(m, t=300)
        self.assertEqual(self.evaluate(m, 301)["measurement_age_seconds"], 1)
        p = packet(ts=1600); del p["params"]["temperature:0"]
        self.assertTrue(m.ingest(p, retained=False, now=600, epoch=1600))
        s = self.evaluate(m, 601)
        self.assertEqual(s["report_age_seconds"], 1)
        self.assertEqual(s["measurement_age_seconds"], 301)

    def test_retained_replayed_wrong_source_and_delayed_packets_rejected(self):
        for kind in ["retained", "source", "old", "future", "replay", "method"]:
            m = self.model(); self.report(m)
            p = packet(ts=1100)
            if kind == "source": p["src"] = "other"
            if kind == "old": p["params"]["ts"] = 900
            if kind == "future": p["params"]["ts"] = 2000
            if kind == "replay": p["params"]["ts"] = 1000
            if kind == "method": p["method"] = "GetStatus"
            self.assertFalse(m.ingest(p, retained=kind == "retained", now=100, epoch=1100), kind)
            self.assertEqual(m.last_report, 0)

    def test_invalid_values_and_missing_entities_stop_even_during_minimum_on(self):
        for invalid in [None, "unknown", float("nan"), float("inf"), True, 60]:
            m = self.model(); self.report(m); self.evaluate(m)
            self.report(m, t=1, temp=invalid)
            self.assertFalse(self.evaluate(m, 1)["simulated_demand"])
            self.assertEqual(self.evaluate(m, 1)["status"], "uncertain")
        m = self.model(); self.report(m); self.evaluate(m)
        self.assertFalse(self.evaluate(m, 1, available=False)["simulated_demand"])

    def test_low_empty_unknown_battery_and_power_mismatch_block(self):
        for bat in [0, 10, None]:
            m = self.model(); self.report(m, battery=bat)
            self.assertFalse(self.evaluate(m)["simulated_demand"])
        m = self.model(); self.report(m, power=True)
        self.assertEqual(self.evaluate(m)["status"], "uncertain")

    def test_early_stop_minimum_times_and_hard_target(self):
        m = self.model(); self.report(m); self.evaluate(m)
        self.report(m, t=60, temp=17.5)
        self.assertTrue(self.evaluate(m, 60)["simulated_demand"])
        self.assertFalse(self.evaluate(m, 180)["simulated_demand"])
        self.report(m, t=181, temp=17.3)
        self.assertFalse(self.evaluate(m, 181)["simulated_demand"])
        self.assertTrue(self.evaluate(m, 780)["simulated_demand"])
        self.report(m, t=781, temp=18)
        self.assertFalse(self.evaluate(m, 781)["simulated_demand"])

    def test_usb_equal_reports_every_five_minutes_and_demand_limit(self):
        m = self.model("usb")
        for t in [0, 300, 600]:
            self.report(m, t=t, temp=17.5, power=True)
            self.assertTrue(self.evaluate(m, t)["simulated_demand"])
        self.report(m, t=900, temp=17.5, power=True)
        self.assertFalse(self.evaluate(m, 900)["simulated_demand"])
        self.assertEqual(self.evaluate(m, 1500)["status"], "uncertain")

    def test_restart_profile_and_away_summer_off_require_fresh_context(self):
        m = self.model(); self.report(m); self.evaluate(m)
        self.assertFalse(self.evaluate(m, 1, home=False)["simulated_demand"])
        restarted = self.model()
        self.assertEqual(self.evaluate(restarted)["status"], "uncertain")
        self.assertFalse(self.evaluate(restarted)["simulated_demand"])
        m.change_profile("usb", 2)
        self.assertFalse(self.evaluate(m, 2)["simulated_demand"])

    def test_unsafe_profile_overrides_rejected(self):
        for values in [{"max_on_seconds": 7200}, {"fresh_seconds": 7200},
                       {"stop_margin": 1}, {"min_on_seconds": 700}]:
            with self.assertRaises(ValueError):
                mod.ReferenceSimulator("test", overrides={"battery": values})

    def test_production_reference_modules_have_no_actuator_calls(self):
        import ast
        root = Path(__file__).parents[1] / "custom_components/heatmiser_wifi"
        for name in ["reference.py", "reference_monitor.py", "reference_sensor.py", "select.py"]:
            tree = ast.parse((root / name).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, ["set_value", "callService", "async_call", "set_temperature"])


if __name__ == "__main__":
    unittest.main()
