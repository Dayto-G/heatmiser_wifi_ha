"""Passive reference-sensor simulator. Contains no device or service writes."""
from dataclasses import dataclass
import math


def number(value, minimum, maximum):
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError):
        return None
    return result if math.isfinite(result) and minimum <= result <= maximum else None


@dataclass(frozen=True)
class Profile:
    fresh_seconds: int
    offline_seconds: int
    start_delta: float
    stop_margin: float
    min_on_seconds: int
    min_off_seconds: int
    max_on_seconds: int


PROFILES = {
    "usb": Profile(600, 1800, .4, .2, 180, 300, 900),
    "battery": Profile(900, 9000, .6, .5, 180, 600, 600),
}


class ReferenceSimulator:
    """Freshness uses incoming non-retained device RPCs, never HA state writes.

    All durations use the caller's monotonic clock. Device wall time is only a
    replay/delay guard. No saved demand or receipt is restored after a restart.
    """

    def __init__(self, source, profile="battery", overrides=None):
        self.source = source
        self.profiles = {**PROFILES}
        for key, values in (overrides or {}).items():
            base = PROFILES[key].__dict__ | values
            p = Profile(**base)
            if not (60 <= p.fresh_seconds <= p.offline_seconds <= 10800
                    and .2 <= p.start_delta <= 2 and 0 <= p.stop_margin < p.start_delta
                    and 60 <= p.min_on_seconds < p.max_on_seconds <= 1800
                    and 60 <= p.min_off_seconds <= 3600):
                raise ValueError("Unsafe simulation profile limits")
            if key == "battery" and (p.max_on_seconds > 600 or p.fresh_seconds > 900):
                raise ValueError("Battery profile exceeds conservative limits")
            self.profiles[key] = p
        self.profile = profile
        self.temperature = self.battery = self.power = None
        self.last_report = self.last_measurement = self.last_epoch = None
        self.last_power = self.last_battery = None
        self.on = False
        self.started = self.stopped = None
        self.locked_measurement = None
        self.invalid = False
        self.reason = "Waiting for a new device report"

    def change_profile(self, value, now):
        if value not in self.profiles:
            raise ValueError("Choose usb or battery")
        self.profile = value
        self._stop(now)
        self.locked_measurement = self.last_measurement

    def ingest(self, payload, *, retained, now, epoch):
        """Accept only a new timestamped notification from the configured device.

        A humidity-only notification is a device heartbeat, not a temperature
        measurement. Invalid temperatures invalidate the reference immediately.
        """
        if retained or not isinstance(payload, dict) or payload.get("src") != self.source:
            return False
        if payload.get("method") not in ("NotifyStatus", "NotifyFullStatus"):
            return False
        params = payload.get("params")
        if not isinstance(params, dict):
            return False
        ts = number(params.get("ts"), 1, epoch + 30)
        if ts is None or epoch - ts > 120 or (self.last_epoch is not None and ts <= self.last_epoch):
            return False
        self.last_epoch = ts
        self.last_report = now
        devicepower = params.get("devicepower:0", {})
        if isinstance(devicepower, dict):
            bat, external = devicepower.get("battery", {}), devicepower.get("external", {})
            if isinstance(bat, dict) and "percent" in bat:
                self.battery = number(bat["percent"], 0, 100)
                self.last_battery = now
            if isinstance(external, dict) and "present" in external:
                self.power = external["present"] if isinstance(external["present"], bool) else None
                self.last_power = now
        temp = params.get("temperature:0")
        if isinstance(temp, dict) and ("tC" in temp or temp.get("errors")):
            self.temperature = number(temp.get("tC"), 0, 40)
            self.invalid = self.temperature is None or bool(temp.get("errors"))
            if not self.invalid:
                self.last_measurement = now
        return True

    def _stop(self, now):
        if self.on:
            self.stopped = now
        self.on = False
        self.started = None

    def evaluate(self, *, now, target, home, available=True):
        p = self.profiles[self.profile]
        report_age = None if self.last_report is None else max(0, now - self.last_report)
        age = None if self.last_measurement is None else max(0, now - self.last_measurement)
        status, reason = "current", "Fresh device temperature report"
        if not available:
            status, reason = "offline", "Reference entity missing, invalid or unavailable"
        elif self.last_report is None:
            status, reason = "uncertain", "No device report received since startup"
        elif report_age >= p.offline_seconds:
            status, reason = "offline", "No device report within the heartbeat grace period"
        elif self.invalid or age is None:
            status, reason = "uncertain", "No valid temperature in a device report"
        elif age >= p.fresh_seconds:
            status, reason = "uncertain", "Temperature too old for simulated demand"
        elif self.power is None:
            status, reason = "uncertain", "Power source has not been confirmed by the device"
        elif self.last_power is None or now - self.last_power >= p.offline_seconds:
            status, reason = "uncertain", "Power source information is too old"
        elif (self.profile == "usb") != self.power:
            status, reason = "uncertain", "Selected profile differs from reported power source"
        elif not self.power and (self.battery is None or self.battery <= 10
                                 or self.last_battery is None or now - self.last_battery >= p.offline_seconds):
            status, reason = "uncertain", "Battery missing or at/below 10 percent"
        target = number(target, 5, 30)
        if status != "current" or not home or target is None:
            self._stop(now)
            if status == "current":
                reason = "Internal Heatmiser: Away, Summer, Off or invalid target"
        elif self.on and now - self.started >= p.max_on_seconds:
            self.locked_measurement = self.last_measurement
            self._stop(now)
            reason = "Maximum simulated demand reached; new measurement and cooldown required"
        elif self.on:
            # Hard target/safety stops override minimum-on time. Predictive
            # early stop is allowed after minimum-on time; never extend a lease.
            if (self.temperature >= target or
                    (now - self.started >= p.min_on_seconds and self.temperature >= target - p.stop_margin)):
                self._stop(now)
                reason = "Early stop for radiator residual heat"
            else:
                reason = "Simulated heat demand (no thermostat write)"
        else:
            cooldown = self.stopped is not None and now - self.stopped < p.min_off_seconds
            fresh_after_limit = self.locked_measurement is None or self.last_measurement > self.locked_measurement
            if not fresh_after_limit:
                reason = "Waiting for a newer measurement after demand limit/profile change"
            elif cooldown:
                reason = "Minimum off-time"
            elif self.temperature <= target - p.start_delta:
                self.on, self.started = True, now
                reason = "Simulated heat demand (no thermostat write)"
            else:
                reason = "Within hysteresis band"
        self.reason = reason
        return {
            "status": status, "reason": reason, "profile": self.profile,
            "mode": "simulation_only", "automatic_control_available": False,
            "temperature": self.temperature, "battery": self.battery,
            "power": "unknown" if self.power is None else "usb" if self.power else "battery",
            "report_age_seconds": report_age, "measurement_age_seconds": age,
            "simulated_demand": int(self.on), "target": target,
            "remaining_demand_seconds": max(0, p.max_on_seconds - (now - self.started)) if self.on else 0,
            "max_on_seconds": p.max_on_seconds,
            "fallback": "Internal Heatmiser remains in control; no external override is sent",
        }
