"""Experimental timed holds for the legacy PRT WiFi protocol.

Write address 32 is distinct from read offsets 31/32 (little endian).
Protocol reference: midstar/heatmiser_wifi/docs/heatmiser_v3_protocol_3.9.pdf.
No thermostat calls occur until an explicitly enabled action is invoked.
"""
from threading import Lock

HOLD_LOCK = Lock()
MODELS = {"PRT", "PRT-E", "PRT-HW"}


def timer_minutes(raw):
    """Decode the timer in a complete DCB response."""
    if len(raw) < 33 or raw[4] not in (2, 3, 4):
        raise ValueError("Timed holds require a PRT, PRT-E or PRT-HW")
    return raw[31] | (raw[32] << 8)


def write_items(client, items):
    """Send one v3 multi-item write and consume its DCB acknowledgement.

    The upstream set_dcb/set_value methods leave this response unread.
    Reusing that socket for a read can otherwise return the previous state.
    """
    payload = bytearray()
    for address, data in items:
        payload.extend(address.to_bytes(2, "little"))
        payload.append(len(data))
        payload.extend(data)
    length = 8 + len(payload)  # opcode, length, PIN, count, payload, CRC
    frame = bytearray([0xA3, length & 255, length >> 8,
                       client.pin & 255, client.pin >> 8, len(items)])
    frame.extend(payload)
    frame.extend(client.crc16.CRC16(frame))
    client.sock.sendall(frame)
    # Private upstream parser validates CRC, opcode and response lengths.
    start, raw = client._receive_dcb()
    if start != 0:
        raise ValueError("Hold response did not contain the whole thermostat state")
    timer_minutes(raw)
    return raw


def read_hold(client):
    """Read the raw timer; upstream get_info currently reverses its bytes."""
    raw = client.get_dcb()
    return timer_minutes(raw)


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
                raw = write_items(client, [(32, b"\x00\x00")])
                if timer_minutes(raw) != 0:
                    raise ValueError("Thermostat did not confirm hold cancellation")
            else:
                if (info.get("temperature_format") != "Celsius"
                        or info.get("on_off") != "On"
                        or info.get("run_mode") != "Heating mode (normal mode)"
                        or info.get("away_mode") != "Off"):
                    raise ValueError("Starting a hold requires Home, heating enabled and Celsius")
                if read_hold(client) != 0:
                    raise ValueError("Cancel the existing hold before starting another")
                timer = duration_minutes.to_bytes(2, "little")
                raw = write_items(client, [(32, timer)])
                if not max(1, duration_minutes - 1) <= timer_minutes(raw) <= duration_minutes:
                    raise ValueError("Timer was not confirmed; target has not been changed")
                # Timer already armed. Set target and timer together using the
                # protocol's item count, rather than separate socket writes.
                raw = write_items(client, [(18, bytes([temperature])), (32, timer)])
                actual_temperature, actual_minutes = raw[18], timer_minutes(raw)
                if actual_temperature != temperature or not 1 <= actual_minutes <= duration_minutes:
                    raise ValueError(
                        f"Hold read-back: requested {temperature} C/{duration_minutes} min, "
                        f"received {actual_temperature} C/{actual_minutes} min; "
                        "inspect thermostat before retrying"
                    )
            return client.get_info()
        finally:
            client.disconnect()
