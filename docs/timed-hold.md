# Experimental timed holds

This branch adds manual actions only. It does not enable Shelly control, alter
schedules, publish a release or install anything on your Home Assistant.

## Enable for a supervised test

After installing this branch, add `enable_experimental_hold: true` to the existing
`heatmiser_wifi:` configuration and restart Home Assistant. Default is false:
neither action is registered until explicitly enabled.

```yaml
action: heatmiser_wifi.hold_on
data:
  temperature: 19
```

Duration defaults to 30 minutes, matching the observed thermostat web interface.
Optionally send `duration_minutes: 15` alongside `temperature: 19` for a 15-minute
hold. Whole minutes from 1 through 30 are accepted by the action; longer holds
are deliberately excluded from this experimental bounded override. The firmware
may reject or round a custom duration: timer read-back must be within one minute
of the requested duration and never exceed it before the target is changed.
Acceptance by the Python action does not prove hardware support. Temperatures must be whole degrees Celsius within configured
min_temp/max_temp limits (and the service range 5–30). Only PRT/PRT-E/PRT-HW are
accepted; starting requires Home and heating enabled. Existing holds must be
cancelled explicitly, so repeated calls cannot silently renew them.

```yaml
action: heatmiser_wifi.hold_off
data: {}
```

Cancellation writes a zero timer and reads it back. It does not force the relay
off, restore a saved target or overwrite the schedule. Verify that the physical
device resumes its current schedule. A successful cancellation alone does not
prove which target the thermostat selects.

## Protocol and failure handling

The legacy v3 protocol uses write address 32 for the two-byte little-endian
hold duration; read offsets 31/32 report it. The upstream Python library's
get_info() reverses those read bytes, so these actions use get_dcb() for timer
verification. The timer is armed and read back BEFORE changing the target. A
failed target write/read leaves the bounded timer in place and raises an error.
Do not blindly retry a failed command: inspect the thermostat first. A failed
cancellation can leave an active hold. Each action uses a separate connection
and hold actions are serialized. Existing legacy polling/setpoint services
are unchanged; do not issue simultaneous manual changes during a test.

Protocol references (facts only; no third-party implementation copied):
- https://github.com/midstar/heatmiser_wifi/blob/master/docs/heatmiser_v3_protocol_3.9.pdf
- https://github.com/thoukydides/heatmiser-wifi/blob/master/bin/heatmiser_wifi.pm

## Required hardware acceptance test

Mock tests verify validation, bytes, command order, rejected read-back and
failure handling; they cannot prove firmware behaviour.

With explicit approval and someone present, start a modest hold (first verify a requested 15-minute countdown),
confirm its target/countdown locally, cancel early and confirm schedule return.
Then repeat and stop HA during the countdown: verify independent expiry on the
physical thermostat. Record target, countdown and relay state before/after.
Also test Home/Away/Summer interactions. Do not rely on these actions for
unattended sensor control until those checks pass. A 30-minute override can
still overheat the room; cancelling a hold does not necessarily stop heating.

There is no automatic renewal, startup hold, Shelly automation or new sensor
in this change. Existing Home/Away/Summer behaviour remains unchanged.
