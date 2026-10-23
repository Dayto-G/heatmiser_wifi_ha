## Changelog

### v1.2.0 - 23 October 2026
- Maintainer-published stable release of the visual schedule editor, including the automatic scale and day/night reference.
- Published from the beta.5 commit; the existing release archive still reports 1.2.0-beta.5 in its manifest.

### v1.2.0-beta.5 - 23 October 2026
- Use a shared automatic temperature scale with 1 °C margins.
- Add subtle day/night backgrounds with a fixed 07:00–22:00 day reference.

### v1.2.0-beta.4 - 23 October 2026
- Register the card in Lovelace storage resources, upgrading its own URL in place.
- Read Celsius from HA configuration when the climate state omits its unit.
- Document adding a shortcut from the new automatic Overview dashboard.

### v1.2.0-beta.3 - 23 October 2026
- Fix services.yaml encoded with Windows-1252 instead of UTF-8.
- Validate UTF-8 for packaged text files in the automated test suite.
- Keep automatic card loading and existing thermostat behaviour unchanged.

### v1.2.0-beta.2 - 23 October 2026
- Automatically serve and load the bundled card after HA startup.
- Add visual entity selectors and matching thermostat discovery in the card picker.
- No manual file copy or Lovelace resource registration required.
- Keep heating active if frontend registration fails; leave user resources intact.

### v1.2.0-beta.1 - 23 October 2026
- Prerelease of the editable weekday/weekend schedule card and validation.
- Bundle the dashboard JavaScript inside the integration for HACS downloads.
- Document beta installation, card setup and return to stable v1.1.2.
- Preserve existing PRT fixes; stable main and v1.1.2 remain unchanged.

### Unreleased
- Align the development manifest version with stable v1.2.0; leave the existing published tag intact.
- Rewrite the README for the Dayto-G fork, document the maintainer-approved stable v1.2.0 release and compatibility limits, and verify unchanged upstream MIT notices.
- Add editable weekday/weekend step graphs, independent saves and device readback.
- Validate chronological schedules and Celsius/5/2 mode before schedule writes.
- Preserve existing PRT fixes and service payload format.

### v1.1.2 - 22 October 2026
- Convert and validate weekday/weekend heating payloads before writing; always disconnect after a write attempt.
- Handle missing hot-water trigger/state keys on heating-only thermostats.
- Set the air-temperature sensor device class and native Celsius unit.
- Update manifest ownership, documentation and issue links for the Dayto-G fork.

### v0.1.1 - Feb 2025

   - Fix deprecated features which were removed in HA Core 2025.1 https://developers.home-assistant.io/blog/2023/12/28/support-feature-magic-numbers-deprecation:
      - TEMP_CELSIUS was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use UnitOfTemperature.CELSIUS instead
      - TEMP_FAHRENHEIT was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use UnitOfTemperature.FAHRENHEIT instead
      - HVAC_MODE_OFF was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use HVACMode.OFF instead
      - HVAC_MODE_HEAT was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use HVACMode.HEAT instead
      - CURRENT_HVAC_OFF was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use HVACAction.OFF instead
      - CURRENT_HVAC_HEAT was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use HVACAction.HEATING instead
      - CURRENT_HVAC_IDLE was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use HVACAction.IDLE instead
      - SUPPORT_TARGET_TEMPERATURE was used from heatmiser_wifi, this is a deprecated constant which will be removed in HA Core 2025.1. Use ClimateEntityFeature.TARGET_TEMPERATURE instead

   - Fix deprecated features which will be removed in HA Core 2025.5:
      - Detected that custom integration 'heatmiser_wifi' accesses hass.helpers.discovery, which should be updated to import functions used from discovery directly at custom_components/heatmiser_wifi/__init__.py, line 55: hass.helpers.discovery.load_platform('climate', DOMAIN, {}, config)

   - Fix other errors / warnings in the logs:
      - Error adding entity sensor.prt_hw_air_temp for domain sensor with platform heatmiser_wifi


### v0.1.0 - May 2024
 - First release of my forked version from the original (https://github.com/midstar/heatmiser_wifi_ha)
