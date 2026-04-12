"""Helpers for storing renewed Hyundai / Kia tokens in a config entry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import CONF_TOKEN


def _normalize_access_token(token_payload: dict[str, Any]) -> str | None:
    """Return an access token in the format expected by hyundai_kia_connect_api."""

    access_token = token_payload.get("access_token")
    token_type = token_payload.get("token_type")
    if not access_token:
        return None
    if isinstance(access_token, str) and access_token.startswith("Bearer "):
        return access_token
    if token_type:
        return f"{token_type} {access_token}"
    return access_token


def _normalize_valid_until(token_payload: dict[str, Any], current_token: dict[str, Any]) -> str | None:
    """Build a fresh valid_until from expires_in when possible."""

    expires_in = token_payload.get("expires_in")
    if expires_in is not None:
        try:
            seconds = int(expires_in)
        except (TypeError, ValueError):
            seconds = None
        if seconds is not None:
            return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()

    return current_token.get("valid_until")


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
    current_token = entry.data.get(CONF_TOKEN, {})
    normalized_access_token = _normalize_access_token(token_payload)
    normalized_valid_until = _normalize_valid_until(token_payload, current_token)

    merged_token = {
        **current_token,
        **token_payload,
    }

    if refresh_token:
        merged_token["password"] = refresh_token
        merged_token["refresh_token"] = refresh_token
        connector = merged_token.get("connector")
        if isinstance(connector, dict):
            for value in connector.values():
                if isinstance(value, dict):
                    value["refresh_token"] = refresh_token

    if normalized_access_token:
        merged_token["access_token"] = normalized_access_token
        connector = merged_token.get("connector")
        if isinstance(connector, dict):
            for value in connector.values():
                if isinstance(value, dict):
                    value["access_token"] = normalized_access_token

    if normalized_valid_until:
        merged_token["valid_until"] = normalized_valid_until

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
