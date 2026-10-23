"""Serve and load the bundled dashboard card without manual resource setup."""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.components.lovelace.const import LOVELACE_DATA
from homeassistant.components.lovelace.resources import ResourceStorageCollection

CARD_PATH = Path(__file__).parent / "frontend" / "heatmiser-schedule-card.js"
CARD_URL = "/heatmiser_wifi/heatmiser-schedule-card.js"
DATA_REGISTERED = "heatmiser_wifi_frontend_registered"
DATA_PATH_REGISTERED = "heatmiser_wifi_frontend_path_registered"


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register on the event loop, after frontend/http dependencies are ready."""
    if hass.data.get(DATA_REGISTERED):
        return
    # Reading the asset happens in the executor, never on HA's event loop.
    content = await hass.async_add_executor_job(CARD_PATH.read_bytes)
    version = sha256(content).hexdigest()[:12]
    if not hass.data.get(DATA_PATH_REGISTERED):
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(CARD_PATH), False)]
        )
        hass.data[DATA_PATH_REGISTERED] = True
    url = f"{CARD_URL}?v={version}"
    lovelace = hass.data.get(LOVELACE_DATA)
    resources = lovelace.get("resources") if isinstance(lovelace, dict) else getattr(lovelace, "resources", None)
    if isinstance(resources, ResourceStorageCollection):
        # Load through the public collection API before looking for an existing
        # entry. Upgrade our own URL in place; leave unrelated resources alone.
        await resources.async_get_info()
        existing = next((item for item in resources.async_items()
                         if item["url"].split("?", 1)[0] == CARD_URL), None)
        if existing is None:
            await resources.async_create_item({"url": url, "res_type": "module"})
        elif existing["url"] != url or existing.get("type") != "module":
            await resources.async_update_item(existing["id"], {"url": url, "res_type": "module"})
    else:
        # YAML resource collections cannot be edited through the storage API.
        frontend.add_extra_js_url(hass, url)
    hass.data[DATA_REGISTERED] = True
