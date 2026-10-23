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

1. In **HACS → Heatmiser WiFi → Redownload → Need a different version?**, select
   **v1.2.0-beta.2**, download and restart Home Assistant.
2. Refresh the browser or reopen the HA app. The integration serves and loads
   the card automatically. No file copy, `www` folder or manual dashboard resource
   is required, for either storage or YAML dashboards.
3. Edit your dashboard, choose **Add card**, search for **Heatmiser heating
   schedule** and select it. The card tries to detect the matching thermostat
   and schedule sensor. Use the two entity selectors to check or change them,
   then save the card.

If you prefer a manual YAML card, replace the example entity IDs:

```yaml
type: custom:heatmiser-schedule-card
entity: sensor.heating_program_mode
climate_entity: climate.heating
```

If you already followed the beta.1 manual setup, remove its old
`/local/heatmiser-schedule-card.js` entry from **Settings → Dashboards → Resources**
(or your YAML resources), then fully refresh the browser. Your existing card
configuration can stay. The copied file in `www` is no longer needed. The
integration does not delete or modify any of your existing resources or files.

The bundled card is served at `/heatmiser_wifi/heatmiser-schedule-card.js` through
Home Assistant's static file API and loaded with a content-based cache version.
No files are copied and no persistent Lovelace resource is created. If UI
registration fails, HA logs the error and the existing heating setup stays active.

The card supports the existing single-thermostat integration, in Celsius and
5/2 program mode (`program_mode` sensor state `0`). It does not change program mode.
Seven-day and hot-water schedules are not edited. Both configured entities must
belong to the same Heatmiser integration. The integration automatically loads the bundled card after startup.

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
  If the card does not appear, restart HA, fully refresh the browser and check the
  Heatmiser logs for card registration errors. If
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

Remove the card from your dashboard to stop showing the editor. If needed,
restore the previous integration version and restart HA. Removing the card does
not restore previously saved thermostat schedules: record them beforehand.

### Testing v1.2.0-beta.2 with HACS

The stable GitHub release v1.1.2 and the main branch are unchanged. Installing a
beta in the same Home Assistant instance replaces that instance's installed
integration files. For side-by-side testing while production keeps running
v1.1.2, use a separate Home Assistant test instance.

1. Back up your HA configuration and record the thermostat's current schedules.
2. In HACS, ensure the repository URL is `Dayto-G/heatmiser_wifi_ha` (the upstream
   `iainbullock` or `midstar` repository will not show this beta). If needed, add
   this repository under Custom repositories with category **Integration**.
3. Open **HACS → Heatmiser WiFi → ⋮ → Redownload → Need a different version?**.
   Enable prerelease/beta versions if your HACS version offers that option, select
   **v1.2.0-beta.2**, then download it. If missing, use **Update information**
   or check for updates, and reopen the download dialog.
4. Restart Home Assistant and refresh the browser. Add **Heatmiser heating
   schedule** from the dashboard card picker. The JavaScript loads automatically.
5. Compare both schedules with the thermostat before editing. Save one deliberate
   change and verify it on the thermostat. This beta supports Celsius and 5/2
   mode only; it does not switch program mode.

To return to stable, use the same Redownload dialog, select **v1.1.2**, download
and restart HA. Remove the beta card from your dashboard if no longer used.
Downgrading the integration does not undo schedule changes written to the device.
