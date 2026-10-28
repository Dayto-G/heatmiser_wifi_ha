"""Experimental timed holds for the legacy PRT WiFi protocol.

Write address 32 is distinct from read offsets 31/32 (little endian).
Protocol reference: midstar/heatmiser_wifi/docs/heatmiser_v3_protocol_3.9.pdf.
No thermostat calls occur until an explicitly enabled action is invoked.
"""
from threading import Lock

HOLD_LOCK = Lock()
MODELS = {"PRT", "PRT-E", "PRT-HW"}


def read_hold(client):
    """Read the raw timer; upstream get_info currently reverses its bytes."""
    raw = client.get_dcb()
    if len(raw) < 33 or raw[4] not in (2, 3, 4):
        raise ValueError("Timed holds require a PRT, PRT-E or PRT-HW")
    return raw[31] | (raw[32] << 8)


def execute_hold(client, temperature=None, minimum=5, maximum=25, duration_minutes=30):
    """Arm and verify the timer BEFORE raising a target; never retry blindly.

    A target-write/read failure leaves the verified timer armed. Cancellation
    clears the timer only; the device determines the resumed schedule target.
    """
    if temperature is not None:
        if type(duration_minutes) is not int or not 1 <= duration_minutes <= 30:
            raise ValueError("Hold duration must be a whole number of minutes from 1 to 30")
        if type(temperature) is not int or not minimum <= temperature <= maximum:
            raise ValueError("Hold temperature must be a whole degree within configured limits")
    with HOLD_LOCK:
        try:
            client.connect()
            info = client.get_info()
            if info.get("model") not in MODELS:
                raise ValueError("Timed holds require a PRT, PRT-E or PRT-HW")
            if temperature is None:
                client.set_dcb(32, bytearray([0, 0]))
                if read_hold(client) != 0:
                    raise ValueError("Thermostat did not confirm hold cancellation")
            else:
                if (info.get("temperature_format") != "Celsius"
                        or info.get("on_off") != "On"
                        or info.get("run_mode") != "Heating mode (normal mode)"
                        or info.get("away_mode") != "Off"):
                    raise ValueError("Starting a hold requires Home, heating enabled and Celsius")
                if read_hold(client) != 0:
                    raise ValueError("Cancel the existing hold before starting another")
                client.set_dcb(32, bytearray(duration_minutes.to_bytes(2, 'little')))
                if not max(1, duration_minutes - 1) <= read_hold(client) <= duration_minutes:
                    raise ValueError("Timer was not confirmed; target has not been changed")
                client.set_value("set_room_temp", temperature)
                result = client.get_info()
                if result.get("set_room_temp") != temperature or not 1 <= read_hold(client) <= duration_minutes:
                    raise ValueError("Hold could not be confirmed; inspect thermostat before retrying")
            return client.get_info()
        finally:
            client.disconnect()
