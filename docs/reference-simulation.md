# Shelly H&T Gen3 reference monitor — experimental, simulation only

## Safety conclusion

The existing Heatmiser `set_room_temp` write is not a device-enforced, expiring
lease. A HA timeout, automation or shutdown handler cannot guarantee restoring a
setpoint after a power loss, HA crash or network failure. The stored heating
schedule does not guarantee an immediate reset of a manual setpoint. Physical
fallback after an external override is therefore **not guaranteed**.

This implementation has **no actuator**: neither profile writes any Heatmiser
setpoint, preset, mode or schedule. There is no switch, configuration value or
service to enable physical control. Internal Heatmiser operation is the fallback
at all times, including HA restarts and sensor outages. This does not restore
setpoints written by unrelated automations; disable any independently created
external controller before evaluating this monitor.

Future physical control requires a separately reviewed design, explicit owner
approval and hardware-backed expiry or another independently verified fallback.
USB power alone does not solve this safety problem. Never connect the simulated
demand sensor to a boiler relay or to setpoint-writing automations.

## Reporting contract

The official H&T Gen3 documentation describes battery reporting at default
temperature/humidity changes of 0.5 °C / 5%, a periodic report after two hours,
and USB reporting about every five minutes. Device firmware, configuration,
network failures and cool-down can affect actual arrival times. These intervals
are not delivery guarantees.

Sources:
- [Shelly H&T Gen3 measuring and reporting](https://kb.shelly.cloud/knowledge-base/shelly-h-t-gen3)
- [Shelly wake-up/report schemes](https://support.shelly.cloud/en/support/solutions/articles/103000226308-wake-up-schemes-and-data-reporting-for-shelly-plus-h-t-and-shelly-gen3-h-t-devices)
- [Temperature RPC component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/Temperature/)
- [DevicePower RPC component](https://shelly-api-docs.shelly.cloud/gen2/ComponentsAndServices/DevicePower/)
- [HA last_reported semantics](https://contributors.home-assistant.io/blog/2024/03/20/state_reported_timestamp/)

`last_changed` tracks value changes. `last_updated` includes attribute changes.
`last_reported` tracks **HA entity writes**, not necessarily fresh device
measurements: an integration can rewrite cached temperatures after another
component updates. The monitor displays the HA timestamp for diagnosis but
**never renews temperature freshness from it**. No timer, profile selection,
UI refresh, unchanged entity write, restored state or humidity-only notification
can make an old temperature fresh.

For authoritative receipts this implementation optionally subscribes to the
device's exact MQTT `events/rpc` topic. Only non-retained `NotifyStatus` /
`NotifyFullStatus` packets from the configured `src` are accepted. The packet
must have a new `params.ts`, no more than 120 seconds old or 30 seconds ahead of
HA. A device clock outside that window is rejected, not silently trusted.
Duplicate, replayed and retained packets are rejected. The local monotonic
receipt clock controls expiry; device timestamps are replay/delay checks.

Two separate ages are recorded:
- A device notification renews the **device report** receipt time.
- Only a notification containing valid `temperature:0.tC` renews the
  **temperature measurement** receipt time. The same numeric value is accepted
  when present in a genuinely new notification. Humidity-only reports do not
  renew it. Explicit temperature errors invalidate the reference immediately.

A timestamped notification is evidence of a reported temperature, not an
independent guarantee of sensor accuracy. Broker security and an accurate HA /
device clock remain prerequisites. Do not use retained telemetry as live input.

Existing Shelly integration/WebSocket use can remain enabled. MQTT is an
additional observation channel, not a replacement control channel. **MQTT is
not enabled or configured on a physical device by this project.** Without the
MQTT receipt channel, HA values remain visible, device-receipt ages are unknown,
status stays uncertain, and simulated external demand is inhibited. This is an
intentional fail-closed limitation, not a claim that the Shelly is disconnected.

## Installation on the development branch

This feature is not included in the existing v1.2.0 archive. Review the draft PR
and use a test installation of this branch before adding optional YAML. No
production release or live heating-control automation is created.

Merge the following optional block into the existing `heatmiser_wifi` YAML;
retain your host, PIN and other settings. Check your actual entity IDs.

```yaml
heatmiser_wifi:
  host: "YOUR_THERMOSTAT_IP"
  friendly_name: "Heating"
  # Keep the other existing configuration options here.
  reference_monitor:
    temperature_entity: sensor.shellytempsensor_temperature
    climate_entity: climate.heating
    profile: battery
    # Optional: leave both absent for HA-only monitoring with uncertain freshness.
    mqtt_source: "shellyhtg3-YOUR_DEVICE_ID"
    mqtt_topic: "shellyhtg3-YOUR_DEVICE_ID/events/rpc"
```

For receipt tracking, configure HA's MQTT integration and a secured local broker
first, then configure Shelly MQTT notifications when it is awake. Read the actual
device ID / topic prefix; do not copy the placeholders. Never publish credentials
in repository examples. No wildcard topics are accepted. An absent broker /
subscription is visible in monitor attributes and cannot produce heat demand.
No network polling is used to wake battery sensors. The manifest lists MQTT as
an optional `after_dependencies`, so it is not required for normal heating.

Add [the dashboard view](../examples/reference-dashboard.yaml) to an editable
dashboard after installing the branch and restarting HA. Check entity IDs if HA
has renamed a collision. The profile selector changes **simulation rules only**.
It neither changes sensor power nor alters the heating schedule. It resets to
the YAML profile after restart; receipt times and simulated demand are not
restored. A new device temperature report is required after startup.

## Profiles and bounds

| Setting | USB-C | Battery |
| --- | ---: | ---: |
| Temperature fresh for simulation | less than 10 min | less than 15 min |
| Device report overdue / offline | 30 min | 150 min |
| Start when temperature at/below target minus | 0.4 °C | 0.6 °C |
| Early stop at target minus | 0.2 °C | 0.5 °C |
| Minimum simulated on-time | 3 min | 3 min |
| Minimum off-time | 5 min | 10 min |
| Maximum continuous simulated demand | 15 min | 10 min |

After 15 minutes a battery reading may still be legitimate for display but is
**uncertain for regulation**. It is not called offline merely because a
five-minute USB interval elapsed. After 150 minutes without a device report,
offline means missing telemetry, not proof that the physical device is dead.
Low/unknown battery (10% or less), missing/invalid temperature, unknown power,
power/profile mismatch and non-Celsius data inhibit simulation. The actual
power indication comes from `devicepower:0.external.present`; battery presence
alone is not used to guess USB connection. HA's cached power/battery entities
are separately labelled in the dashboard.

Min-on time applies to predictive early stops. Hard target, invalid/stale data,
Away/Summer/Off and maximum-demand expiry override minimum-on immediately.
Fresh reports never extend an already-started maximum demand window. At the
limit, demand stops and requires **both a newer temperature report and the
minimum off-time** before another start. The HA watchdog ticks every 15 seconds,
so simulated transitions can be delayed by up to a tick in a healthy event loop.
The core engine also evaluates on incoming notifications and entity changes.

The target is read from the existing Heatmiser climate entity. Only Heat mode
and Home preset allow simulation. Away, Summer, Off, missing/invalid target and
unavailable climate data stop simulation. No preset is changed. Schedule changes
are reflected when HA receives the resulting target. Schedule and preset
semantics remain owned by Heatmiser, including any manually applied overrides.

Profile overrides can be provided under `reference_monitor.profiles`, e.g.:

```yaml
profiles:
  usb:
    start_delta: 0.5
    stop_margin: 0.2
  battery:
    max_on_seconds: 480
    min_off_seconds: 900
```

The engine validates ranges. Battery freshness cannot exceed 900 seconds and
battery maximum demand cannot exceed 600 seconds. Stop margin must be smaller
than start delta. Values are conservative simulation hypotheses, **not tuned
physical control recommendations**. In particular, the 0.5 °C battery early-stop
margin is motivated by observed radiator afterheat but must be validated with
reference measurements. No unseen room-temperature trend is interpolated.

## Required scenario and tests

For a reported 17.5 °C and target 18 °C, the battery profile does not start
simulated demand (start threshold is 17.4 °C). If the actual room rises unseen
to 18 °C, the simulator keeps displaying the last reported 17.5 °C and marks it
uncertain at 15 minutes. It does not invent a reading or keep heating for two
hours. A separate test starts from 17.3 °C: without a new report, simulated
demand stops at 10 minutes and cannot rearm from the old low reading. In USB
mode 17.5 °C would start simulated demand, but fresh five-minute reports still
cannot extend its 15-minute maximum.

Run `python -m unittest discover -s tests` and `node --test tests/card.test.js`.
Tests cover equal-value receipts, humidity-only reports, retained/replayed/
wrong-source/delayed notifications, invalid/NaN data, disconnects, battery
faults, profile changes, min/max durations, early stops, restarts and preset
inhibition. No test performs a physical thermostat write.

## Live inspection (28 October 2026)

Read-only inspection of the maintainer's H&T Gen3 found firmware 1.4.5,
battery 100%, external power off, temperature offset 0 °C, report threshold
0.5 °C, humidity offset 0%, humidity threshold 5%. Cloud and MQTT were disabled;
an outbound WebSocket to the local HA instance was enabled. No setting was
changed. The web UI showed an available firmware update; none was installed.

HA showed the temperature unchanged since 13:38 at 17.5 °C, with a newer entity
report at 15:38, while humidity also updated. This confirms reports/HA writes
can occur without a temperature value change; it does not prove that the
WebSocket packet included a new temperature measurement. Waking the sensor
allowed its current settings to be read. Full two-hour heartbeat delivery,
five-minute USB delivery and raw notification contents still require a recorded
on-device test in each power mode. The MQTT receipt path is tested with fixtures
and is **not yet verified on this physical device**.
