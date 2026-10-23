"""Validation shared by schedule service and tests (no device I/O)."""


def validate_schedule(trigger, raw):
    """Return four ordered hour/minute/temperature triples as a flat list."""
    if trigger not in ("weekday_triggers", "weekend_triggers"):
        raise ValueError("Unsupported schedule type")
    if not isinstance(raw, str):
        raise ValueError("Schedule values must be a comma-separated string")
    parts = raw.split(",")
    # Existing sensor attributes include one trailing comma.
    if parts[-1].strip() == "":
        parts.pop()
    if len(parts) != 12 or any(not part.strip() for part in parts):
        raise ValueError("Expected exactly 12 integer values")
    values = [int(part.strip()) for part in parts]
    previous = -1
    for i in range(0, 12, 3):
        hour, minute, temp = values[i:i + 3]
        if not (0 <= hour <= 23 and minute in (0, 30) and 5 <= temp <= 30):
            raise ValueError("Use hours 0–23, minutes 0/30 and temperatures 5–30 °C")
        current = hour * 60 + minute
        if current <= previous:
            raise ValueError("Schedule times must be strictly increasing")
        previous = current
    return values
