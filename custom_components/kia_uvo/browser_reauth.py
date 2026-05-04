"""Helpers for Europe browser-based reauthentication experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests


class BrowserReauthError(RuntimeError):
    """Raised when the browser-based token exchange fails."""


@dataclass(frozen=True, slots=True)
class BrowserReauthConfig:
    """Brand-specific browser reauthentication configuration."""

    brand_key: str
    login_host: str
    token_host: str
    login_flow: str
    login_client_id: str
    login_redirect_uri: str
    token_client_id: str
    token_client_secret: str
    token_redirect_uri: str
    token_grant_type: str


BRAND_CONFIGS: dict[str, BrowserReauthConfig] = {
    "hyundai": BrowserReauthConfig(
        brand_key="hyundai",
        login_host="https://idpconnect-eu.hyundai.com",
        token_host="https://idpconnect-eu.hyundai.com",
        login_flow="hyundai_legacy",
        login_client_id="peuhyundaiidm-ctb",
        login_redirect_uri="https://ctbapi.hyundai-europe.com/api/auth",
        token_client_id="6d477c38-3ca4-4cf3-9557-2a1929a94654",
        token_client_secret="KUy49XxPzLpLuoK0xhBC77W6VXhmtQR9iQhmIFjjoY4IpxsV",
        token_redirect_uri="https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token",
        token_grant_type="authorization_code",
    ),
    "kia": BrowserReauthConfig(
        brand_key="kia",
        login_host="https://idpconnect-eu.kia.com",
        token_host="https://idpconnect-eu.kia.com",
        login_flow="kia_eu",
        login_client_id="fdc85c00-0a2f-4c64-bcb4-2cfb1500730a",
        login_redirect_uri="https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect",
        token_client_id="fdc85c00-0a2f-4c64-bcb4-2cfb1500730a",
        token_client_secret="secret",
        token_redirect_uri="https://prd.eu-ccapi.kia.com:8080/api/v1/user/oauth2/redirect",
        token_grant_type="refresh_token",
    ),
}


def normalize_brand(brand: str | None) -> str:
    """Normalize brand input into a supported lowercase key."""

    if not brand:
        return "hyundai"

    brand_key = brand.strip().lower()
    if brand_key not in BRAND_CONFIGS:
        raise BrowserReauthError(f"Unsupported brand for browser reauth: {brand}")
    return brand_key


def get_brand_config(brand: str | None) -> BrowserReauthConfig:
    """Return the brand-specific browser reauth configuration."""

    return BRAND_CONFIGS[normalize_brand(brand)]


def brand_requires_secondary_authorize(brand: str | None) -> bool:
    """Return whether the brand requires a second authorize step."""

    return get_brand_config(brand).login_flow == "hyundai_legacy"


def build_login_url(
    *,
    brand: str | None = None,
    state: str,
    language: str = "en",
    ui_locales: str = "en-US",
    captcha: bool = True,
) -> str:
    """Build the brand-specific login URL used to establish a browser session."""

    config = get_brand_config(brand)
    if config.login_flow == "kia_eu":
        params = {
            "response_type": "code",
            "client_id": config.login_client_id,
            "redirect_uri": config.login_redirect_uri,
            "lang": language,
            # Kia EU expects a stable ccsp state value.
            "state": "ccsp",
        }
        return f"{config.login_host}/auth/api/v2/user/oauth2/authorize?{urlencode(params)}"

    params = {
        "client_id": config.login_client_id,
        "redirect_uri": config.login_redirect_uri,
        "nonce": "",
        "state": state,
        "scope": "openid profile email phone",
        "response_type": "code",
        "connector_client_id": config.login_client_id,
        "connector_scope": "",
        "connector_session_key": "",
        "country": "",
        "captcha": 1 if captcha else 0,
        "ui_locales": ui_locales,
        "lang": language,
    }
    return f"{config.login_host}/auth/api/v2/user/oauth2/authorize?{urlencode(params)}"


def build_token_authorize_url(
    *,
    brand: str | None = None,
    state: str,
    language: str = "en",
) -> str | None:
    """Build the authorize URL that yields the code used for token exchange."""

    config = get_brand_config(brand)
    if not brand_requires_secondary_authorize(config.brand_key):
        return None

    params = {
        "response_type": "code",
        "client_id": config.token_client_id,
        "redirect_uri": config.token_redirect_uri,
        "lang": language,
        "state": state,
    }
    return f"{config.token_host}/auth/api/v2/user/oauth2/authorize?{urlencode(params)}"


def exchange_code_for_token(
    code: str,
    *,
    brand: str | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Exchange a brand-specific authorization code for a token payload."""

    config = get_brand_config(brand)
    data: dict[str, str] = {
        "grant_type": config.token_grant_type,
        "client_id": config.token_client_id,
        "client_secret": config.token_client_secret,
    }
    if config.token_grant_type == "refresh_token":
        data["refresh_token"] = code
    else:
        data["code"] = code
        data["redirect_uri"] = config.token_redirect_uri

    response = requests.post(
        f"{config.token_host}/auth/api/v2/user/oauth2/token",
        data=data,
        timeout=timeout,
    )

    try:
        payload = response.json()
    except ValueError as err:
        raise BrowserReauthError(
            f"Token endpoint returned non-JSON response: HTTP {response.status_code}"
        ) from err

    if response.status_code != 200:
        raise BrowserReauthError(
            f"{config.brand_key} token endpoint returned HTTP {response.status_code}: {payload}"
        )

    if "refresh_token" not in payload:
        raise BrowserReauthError(
            f"Token response does not contain refresh_token: {payload}"
        )

    return payload
