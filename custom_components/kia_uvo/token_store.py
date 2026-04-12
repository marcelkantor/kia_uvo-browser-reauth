"""Helpers for storing renewed Hyundai / Kia tokens in a config entry."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN


async def async_store_token_and_reload(
    hass: HomeAssistant,
    entry: ConfigEntry,
    token_payload: dict[str, Any],
) -> None:
    """Persist a renewed token into the config entry and reload the entry.

    Hyundai Europe uses the refresh token as the effective password for the
    token-based login path, so we update both the top-level password and the
    token payload stored in the config entry.
    """

    refresh_token = token_payload.get("refresh_token")

    merged_token = {
        **entry.data.get(CONF_TOKEN, {}),
        **token_payload,
    }

    updates: dict[str, Any] = {
        CONF_TOKEN: merged_token,
    }

    if refresh_token:
        updates[CONF_PASSWORD] = refresh_token

    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, **updates},
    )
    await hass.config_entries.async_reload(entry.entry_id)
