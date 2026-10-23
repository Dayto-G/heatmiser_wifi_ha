# Heatmiser WiFi for Home Assistant — Dayto-G fork

[![HACS custom repository](https://img.shields.io/badge/HACS-Custom_repository-blue.svg)](https://www.hacs.dev/docs/faq/custom_repositories/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE.txt)

This is [Dayto-G's fork](https://github.com/Dayto-G/heatmiser_wifi_ha) of the local-polling Heatmiser WiFi custom integration for Home Assistant. It builds on [Iain Bullock's fork](https://github.com/iainbullock/heatmiser_wifi_ha) of [Joel Midstjärna's original integration](https://github.com/midstar/heatmiser_wifi_ha). This repository maintains fixes for legacy WiFi thermostats and develops a visual heating schedule editor. It is a community project, not an official Heatmiser product.

## Release status

| Version / branch | Status |
| --- | --- |
| [v1.1.2](https://github.com/Dayto-G/heatmiser_wifi_ha/releases/tag/v1.1.2) / `main` | Stable baseline for this fork; no bundled schedule editor. |
| `feat/visual-heating-schedule` / [PR #1](https://github.com/Dayto-G/heatmiser_wifi_ha/pull/1) | Schedule-editor development; **beta**, pending testing and review. |
| [v1.2.0](https://github.com/Dayto-G/heatmiser_wifi_ha/releases/tag/v1.2.0) | Currently published on GitHub without the pre-release flag, but its integration manifest is **1.2.0-beta.5**. Treat the schedule editor in this release as **beta**. |

The release labels and manifest version above were checked on 23 October 2026. Do not rely on GitHub's “Latest” label to choose the stable baseline: explicitly select **v1.1.2** for stable use. The former `v1.2.0-beta.5` release link is no longer present in the release list; the same code is currently tagged `v1.2.0`. Earlier beta releases remain available. This documentation does not change any release labels or tags.

## Supported devices and features

This integration uses the legacy **Heatmiser WiFi** protocol through the `heatmiser_wifi` Python package. Support inherited from upstream is not a claim that every model and firmware has been retested in this fork.

| Model | Support and limits |
| --- | --- |
| DT / DT-E WiFi | Basic temperature and heating controls inherited from Joel's integration; the schedule editor is intended for programmable models exposing four heating periods. |
| PRT / PRT-E WiFi | Programmable thermostat support inherited from Joel's integration. The beta editor requires Celsius and weekday/weekend (5/2) mode. PRT schedule display and editing controls have been smoke-tested on the maintainer's installation; physical schedule writes remain a deliberate user test. |
| PRT-HW WiFi | Support and additional heating/hot-water data inherited from Iain's fork. The beta card edits **heating only**, not hot-water schedules. |

Features depend on the thermostat model and firmware:

- Read room temperature and heating status; read/set the target temperature and heating on/off.
- Home, Away and Summer presets; frost-protection temperature number and key-lock switch.
- Program-mode and date/time sensors; heating and, where exposed by the device, hot-water schedule attributes.
- `heatmiser_wifi.set_value`, `heatmiser_wifi.update_date_time` and `heatmiser_wifi.update_triggers` actions. In this fork, `update_triggers` accepts weekday/weekend **heating** schedules only.

One thermostat is configured by the current YAML schema. Multiple thermostats, Neo/neoHub and other device families are not supported by this implementation. For wired RS232/RS485 Heatmiser systems, see the separate [Home Assistant Heatmiser integration](https://www.home-assistant.io/integrations/heatmiser/); it is not this WiFi custom integration.

## Home Assistant compatibility

Configuration is **YAML-based**; there is no UI configuration flow under “Add integration”. The thermostat must be reachable from Home Assistant on your local network (default port **8068**).

The code includes the upstream migrations to `UnitOfTemperature`, `HVACMode`, `HVACAction`, `ClimateEntityFeature` and directly imported discovery helpers for API removals in HA 2025.1/2025.5. This does **not** establish a tested minimum version or promise compatibility with every HA release. Neither the integration manifest nor `hacs.json` currently declares a minimum HA version.

The beta frontend uses HA's `StaticPathConfig`, Lovelace resource storage and frontend module APIs. Display, entity selection, refresh and unsaved editing have been checked on the maintainer's live PRT installation. There is no full HA-version/model/firmware test matrix. CI runs isolated Python 3.13 and Node.js 22 tests; those tests stub HA interfaces and do not replace running HA or physical thermostat tests. When reporting an issue, include your exact HA Core version, integration version, model, firmware if known, program mode and relevant logs.

## Fixes included in v1.1.2

Compared with Iain's upstream baseline, this fork's [v1.1.2 changes](https://github.com/Dayto-G/heatmiser_wifi_ha/compare/e07c4ed12137b92714943306af84a17dbc34b916...v1.1.2) include:

- Convert the comma-separated heating schedule payload into integers before writing it; validate exactly four hour/minute/temperature triples, supported weekday/weekend trigger names, hours 0–23, minutes 0/30 and temperatures 5–30 °C. Disconnect in `finally` after the write attempt.
- Avoid missing-key errors for thermostats without hot-water support by handling absent weekday/weekend hot-water triggers and `hot_water_state`.
- Declare the air-temperature sensor's temperature device class and native Celsius unit.
- Point integration ownership, documentation and issue links to Dayto-G's fork and set the manifest version to 1.1.2.

The beta retains these fixes and adds stricter chronological schedule validation, device mode/unit checks and readback verification. Those extra protections and the dashboard card are **beta additions**, not features shipped in v1.1.2.

## Installation

### HACS — this fork

1. Install and configure [HACS](https://www.hacs.dev/) if needed.
2. Open **HACS → ⋮ → Custom repositories**. Add `https://github.com/Dayto-G/heatmiser_wifi_ha`, choose type **Integration**, then **Add**. See the [HACS custom repository instructions](https://www.hacs.dev/docs/faq/custom_repositories/).
3. Open **Heatmiser WiFi** and check that the repository/owner is **Dayto-G**, not `iainbullock` or `midstar`.
4. Download the desired version. For the stable baseline, explicitly select **v1.1.2** in the download/version dialog. For an existing installation use **⋮ → Redownload → Need a different version?**. Labels vary slightly with HACS versions.
5. Add or retain the YAML configuration below, check the configuration and **restart Home Assistant**. Downloading with HACS alone does not configure or load this YAML integration.

All forks use the same `custom_components/heatmiser_wifi` directory and domain. A download replaces the integration installed in that HA instance; forks and beta/stable versions cannot run side by side there. Keep a backup before switching, preserve your YAML configuration and avoid having another HACS repository manage the same directory. Use a separate HA test instance if production must stay on v1.1.2.

### Manual installation

Download the chosen release source archive and copy **the entire** `custom_components/heatmiser_wifi` directory into your HA configuration directory's `custom_components` folder. The final manifest path must be `/config/custom_components/heatmiser_wifi/manifest.json` on a typical HA OS installation, without an extra nested directory. Include the `frontend` subdirectory for beta versions. Configure YAML and restart HA. HACS is the preferred route for update tracking.

## Configuration

Merge this into `configuration.yaml`; use your thermostat's address and configured PIN:

```yaml
heatmiser_wifi:
  host: "192.168.1.50"
  port: 8068
  pin: 0
  friendly_name: "Heating"
  min_temp: 5
  max_temp: 25
  step_temp: 1
```

| Option | Required | Default | Meaning |
| --- | --- | --- | --- |
| `host` | Yes | — | Thermostat IP address or hostname. |
| `port` | No | `8068` | Thermostat connection port. |
| `pin` | No | `0` | Thermostat PIN; replace with the device's value. |
| `friendly_name` | No | `Heatmiser <model>` | Entity display name; setting an explicit name makes card setup clearer. |
| `min_temp` / `max_temp` | No | `5` / `25` | Climate entity target-temperature control limits. |
| `step_temp` | No | `1` | Climate entity target-temperature control step. |

These climate control limits do not redefine the beta schedule editor's validation range. Entity IDs depend on the name and your existing entity registry. With `friendly_name: "Heating"`, typical IDs are `climate.heating` and `sensor.heating_program_mode`; check your actual IDs rather than assuming them.

## Visual heating schedule — BETA

The bundled `heatmiser-schedule-card` shows two editable temperature step charts, with **four periods for weekdays and four for the weekend**. It uses the existing `heatmiser_wifi.update_triggers` action and the program-mode sensor's schedule attributes; it does not create a new schedule entity.

Requirements: the current single-thermostat integration, **Celsius**, **5/2 mode** (`program_mode` sensor state `0`) and valid weekday/weekend heating attributes. The card does not change program mode and does not edit seven-day or hot-water schedules. Both selected entities must belong to the same Heatmiser thermostat. Fahrenheit operation of the existing climate entity does not imply Fahrenheit support in this editor.

### Installation and dashboard setup

1. Back up your HA configuration and record the thermostat's schedules.
2. In **HACS → Heatmiser WiFi → ⋮ → Redownload → Need a different version?**, explicitly select **v1.2.0** for the current beta.5 code, subject to the release-status discrepancy above. Earlier pre-release versions can also be selected; enable beta/prerelease visibility if your HACS version offers it. If a version is missing, use **Update information** and reopen the download dialog.
3. Download, **restart Home Assistant**, wait for the integration to become available, then refresh the browser or reopen the HA app.
4. On an editable dashboard, choose **Edit dashboard → Add card → Heatmiser heating schedule**. Check the automatically suggested thermostat and schedule-sensor entities, then save the card.

No JavaScript file copy, `www` folder or manual resource entry is needed. The integration serves the bundled module at `/heatmiser_wifi/heatmiser-schedule-card.js` with a content-based cache version. It creates or updates its own resource in Lovelace storage mode and uses HA's extra-module loader in YAML resource mode. Unrelated resources and user files are left alone; frontend-registration failure is logged without deliberately disabling heating.

If you followed the beta.1 manual setup, remove the old `/local/heatmiser-schedule-card.js` resource from **Settings → Dashboards → Resources** (or YAML resources) and fully refresh. The old copied file is no longer used; your card configuration can stay.

Manual card configuration, using your actual entity IDs:

```yaml
type: custom:heatmiser-schedule-card
entity: sensor.heating_program_mode
climate_entity: climate.heating
```

### Built-in Overview dashboard

The new automatic Overview supports favourite entities, summaries and shortcuts rather than arbitrary custom cards. Create a dashboard from scratch, for example **Heating**, add the card there and use **Edit Overview → Summaries → Add shortcut** to reach it from Overview. Older manually managed Overview dashboards can use the normal card editor.

The `Heating_program_mode` sensor is needed as a data source; it does not need its own visible tile. Removing a favourite or disabling suggested entities does not remove the underlying sensor.

### Charts

Both charts share an automatic temperature scale spanning the lowest and highest valid scheduled temperatures, with **1 °C margin** above and below. It updates during editing; a 16–18 °C schedule is shown on a 15–19 °C scale. The time axis stays **00:00–24:00**.

Subtle light shading marks **07:00–22:00**, with darker shading outside those hours. Boundary labels mark 07:00 and 22:00. These are fixed visual day/night references, **not** astronomical sunrise/sunset, thermostat mode changes or heating commands.

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

## Troubleshooting and rollback

- **Card not found / configuration error:** wait until startup finishes, refresh the browser, confirm the installed version and check HA logs for frontend-registration errors. The editor is a custom card, not an entity in the entity picker.
- **No schedules / unavailable:** check both entity IDs, thermostat connectivity, Celsius and 5/2 mode. Use **Reload and discard changes** after startup.
- **UTF-8 error in `services.yaml`:** older beta builds had a Windows-1252 encoding issue, fixed in beta.3. Download the current test code and restart HA; do not copy the older metadata file over it.
- **Returning to stable:** select **v1.1.2** via HACS Redownload, restart HA and remove the beta card if no longer wanted. Downgrading does not undo schedule values already written to the thermostat. Restore device schedules deliberately if required.

Report problems in [this fork's issue tracker](https://github.com/Dayto-G/heatmiser_wifi_ha/issues). Remove credentials and other private details from logs before posting them.

## Authors, upstream projects and license

- **Joel Midstjärna** wrote the [original Heatmiser WiFi HA integration](https://github.com/midstar/heatmiser_wifi_ha) and the [original Python protocol library](https://github.com/midstar/heatmiser_wifi).
- **Iain Bullock** extended the [HA integration](https://github.com/iainbullock/heatmiser_wifi_ha) with PRT-HW support, sensors, presets and services, and maintains a [protocol-library fork](https://github.com/iainbullock/heatmiser_wifi). The integration manifest currently depends on the package named `heatmiser_wifi`; it does not pin a GitHub library fork.
- **Dayto-G** maintains this fork's v1.1.2 fixes, schedule-editor development and documentation.

The integration is distributed under the **MIT License**. The complete [LICENSE.txt](LICENSE.txt) retains the upstream notices **Copyright (c) 2019 Joel Midstjärna** and **Copyright (c) 2023 Iain Bullock**, together with the permission and warranty text. Retain those notices and the MIT permission text in copies or substantial portions of the software. The existing `LICENSE.txt` is the license file; a duplicate `LICENSE` is not needed.

Upstream funding attribution is retained in [.github/FUNDING.yml](.github/FUNDING.yml). To support Iain's upstream work, see [Iain Bullock on Buy Me a Coffee](https://www.buymeacoffee.com/iainbullock).
