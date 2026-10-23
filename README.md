# Heatmiser WiFi Home Assistant Custom Component

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)

This repository is forked from the original (https://github.com/midstar/heatmiser_wifi_ha) and updated for my personal requirements only. Feel free to use it as is or clone 
and take over the responsibility for public maintenance.

<a href="https://www.buymeacoffee.com/iainbullock" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## Overview
A [Heatmiser](http://www.heatmiser.com/) WiFi Thermostat Home Assistant custom component.

The original version supports:
* Read current air temperature
* Read/set temperature setting (i.e. wanted temperature)
* Read/set on/off of the Thermostat

The original version supports Heatmiser Thermostats are WiFi versions of DT, DT-E, PRT and PRT-E. 

This fork adds support for the PRT-HW WiFi thermostat, and adds the following functionality (for PRT-HW, maybe others):
* Various additional sensors in particular to read trigger times and temperatures for heating, and trigger times for hot water 
* Services to write to various parameters including triggers for heating and hot water
* Set date & time (with an offset if required)
* Set frost temperature using its own number entity
* Switch entity for key lock
* Correct (IMHO) the implementation of Climate Presets, and add a 'Summer' preset. The presets now mimic the same functions as found in the Heatmiser iPhone App

Note that non-WiFi thermostat versions (i.e. using RS-485 serial bus) 
connected through an Heatmiser Ethernet HUB are supported by the
[Home Assistant Heatmiser Core component](https://www.home-assistant.io/integrations/heatmiser/)

## Installation
Install through [HACS](https://hacs.xyz/) using this Custom Repository: https://github.com/iainbullock/heatmiser_wifi_ha

Alternatively copy the heatmiser_wifi directory and its contents to the 
Home Assistant custom_components directory.

## Configuration
Add following configuration to Home Assistant configuration.yaml

    heatmiser_wifi:
      host:          <mandatory - hostname or ip address>
      port:          <optional  - default 8068>
      pin:           <optional  - default 0>
      friendly_name: <optional  - default 'Heatmiser MODELNO'>
  
## See also
* [Heatmiser Wifi HA](https://github.com/midstar/heatmiser_wifi_ha) No longer maintained. This project is forked from here. 
* [Heatmiser Wifi](https://github.com/midstar/heatmiser_wifi) The library used for communication with Heatmiser WiFi. I've created a fork of this to add the required functionality (https://github.com/iainbullock/heatmiser_wifi).
* [daveNewcastle/Heatmiser-WIFI](https://github.com/daveNewcastle/Heatmiser-WIFI) Heatmiser Wifi Home Assistant Component for older versions of Home Assistant. It has not been updated for many years.
* [Home Assistant Heatmiser Core component](https://www.home-assistant.io/integrations/heatmiser/) for non WiFi versions of Heatmister Thermostats.
 
## Author and license
This component was originally written by Joel Midstjärna and licensed under the MIT License. This fork is updated by Iain Bullock and licensed under the MIT License.

## Visual heating schedule (weekdays/weekend)

The `frontend/heatmiser-schedule-card.js` card displays two editable step charts.
It uses the existing `heatmiser_wifi.update_triggers` service and
`*_program_mode` sensor. The card has no external JavaScript dependencies.

### Installation and dashboard setup

1. Install the modified integration from this branch in
   `/config/custom_components/heatmiser_wifi/`, including `schedule.py`, and restart HA.
2. Copy `frontend/heatmiser-schedule-card.js` to
   `/config/www/heatmiser-schedule-card.js` (create `www` if needed).
3. Under **Settings → Dashboards → Resources**, add a JavaScript module:
   `/local/heatmiser-schedule-card.js?v=1`. For later updates, change the version
   parameter and refresh the browser cache. For YAML-managed resources:

   ```yaml
   lovelace:
     resources:
       - url: /local/heatmiser-schedule-card.js?v=1
         type: module
   ```

4. Find the actual entity IDs under **Developer Tools → States**. Add a manual
   dashboard card, replacing both example IDs:

   ```yaml
   type: custom:heatmiser-schedule-card
   entity: sensor.heating_program_mode
   climate_entity: climate.heating
   ```

The card supports the existing single-thermostat integration, in Celsius and
5/2 program mode (`program_mode` sensor state `0`). It does not change program mode.
Seven-day and hot-water schedules are not edited. Both configured entities must
belong to the same Heatmiser integration. HACS does not automatically install
this frontend card as a dashboard resource.

### Editing, saving and verifying

- Edit the four times and temperatures below each chart. Charts show temperature
  setpoints, not measured room temperature. Valid values: four strictly increasing
  times from 00:00 to 23:30, minutes 00/30 and whole degrees from 5–30 °C.
  Both the card and service validate these values before writing.
- Until the first period, yesterday’s final temperature remains in effect.
  The solid line uses the previous day group (Monday/Saturday); the dashed line
  uses the current day group (Tuesday–Friday/Sunday). This is a weekly setpoint
  schedule. Away, Summer, temporary overrides and actual heat demand can affect
  the thermostat’s active behaviour.
- **Save weekdays** and **Save weekend** each write only one group. The service
  checks program mode and units first, then reads the thermostat after writing.
  The card refreshes the climate entity followed by the program sensor and
  compares the returned values. It reports success only if they match.
  Saving both groups is not an atomic transaction.
- **Reload and discard changes** reads the thermostat and replaces local edits
  for both groups. Normal HA updates preserve unsaved edits. A detected external
  schedule change blocks saving until you reload. This is not an atomic lock:
  changes made on the thermostat between checking and writing can still be
  overwritten.
- After a connection error, a write may already have been applied. The card keeps
  your edits and does not report success; reload and check before saving again.
  If the card does not appear, check the resource URL and browser cache. If
  schedules are missing, check entity IDs, availability and 5/2 mode.

Example of the same existing service under **Developer Tools → Actions**:

```yaml
action: heatmiser_wifi.update_triggers
data:
  trigger: weekday_triggers
  values: "6,30,20,8,0,17,17,0,21,22,30,16"
```

### Validation and rollback

Run `python -m unittest discover -s tests` and `node --test tests/card.test.js`.
The tests do not use a real thermostat. After installation, compare the displayed
values with the thermostat, deliberately save one group and check it again on the
thermostat. Final end-to-end validation requires a physical Heatmiser and HA.

Remove the card and dashboard resource to roll back the interface. If needed,
restore the previous integration version and restart HA. Removing the card does
not restore previously saved thermostat schedules: record them beforehand.
