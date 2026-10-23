"""Serve and load the bundled dashboard card without manual resource setup."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

CARD_PATH = Path(__file__).parent / "frontend" / "heatmiser-schedule-card.js"
CARD_URL = "/heatmiser_wifi/heatmiser-schedule-card.js"
DATA_REGISTERED = "heatmiser_wifi_frontend_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register on the event loop, after frontend/http dependencies are ready."""
    if hass.data.get(DATA_REGISTERED):
        return
    # Reading the asset happens in the executor, never on HA's event loop.
    content = await hass.async_add_executor_job(CARD_PATH.read_bytes)
    version = sha256(content).hexdigest()[:12]
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(CARD_PATH), False)]
    )
    # This HA API loads an ES module in both storage and YAML dashboards.
    # No persistent Lovelace resources or user configuration files are edited.
    frontend.add_extra_js_url(hass, f"{CARD_URL}?v={version}")
    hass.data[DATA_REGISTERED] = True
