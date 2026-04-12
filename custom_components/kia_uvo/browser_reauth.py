"""Helpers for Hyundai Europe browser-based reauthentication experiments."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

import requests


HYUNDAI_IDP_BASE_URL = "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2"

# First-party login client used by Hyundai's login page.
LOGIN_CLIENT_ID = "peuhyundaiidm-ctb"
LOGIN_REDIRECT_URI = "https://ctbapi.hyundai-europe.com/api/auth"

# Token client used by the Hyundai / Kia API.
TOKEN_CLIENT_ID = "6d477c38-3ca4-4cf3-9557-2a1929a94654"
TOKEN_CLIENT_SECRET = "KUy49XxPzLpLuoK0xhBC77W6VXhmtQR9iQhmIFjjoY4IpxsV"
TOKEN_REDIRECT_URI = "https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token"


class BrowserReauthError(RuntimeError):
    """Raised when the browser-based token exchange fails."""


def build_login_url(
    *,
    state: str,
    language: str = "en",
    ui_locales: str = "en-US",
    captcha: bool = True,
) -> str:
    """Build the Hyundai login URL used to establish a browser session.

    This mirrors the observed login URL used by the external token solution.
    It does not itself yield the final token exchange code; it only authenticates
    the browser session with Hyundai's identity provider.
    """

    params = {
        "client_id": LOGIN_CLIENT_ID,
        "redirect_uri": LOGIN_REDIRECT_URI,
        "nonce": "",
        "state": state,
        "scope": "openid profile email phone",
        "response_type": "code",
        "connector_client_id": LOGIN_CLIENT_ID,
        "connector_scope": "",
        "connector_session_key": "",
        "country": "",
        "captcha": 1 if captcha else 0,
        "ui_locales": ui_locales,
        "lang": language,
    }
    return f"{HYUNDAI_IDP_BASE_URL}/authorize?{urlencode(params)}"


def build_token_authorize_url(*, state: str, language: str = "en") -> str:
    """Build the authorize URL that yields the code used for token exchange.

    Important: the redirect URI is intentionally Hyundai's known token redirect.
    Using a Home Assistant callback URL here is expected to fail for Hyundai
    Europe due to redirect URI validation on the token endpoint.
    """

    params = {
        "response_type": "code",
        "client_id": TOKEN_CLIENT_ID,
        "redirect_uri": TOKEN_REDIRECT_URI,
        "lang": language,
        "state": state,
    }
    return f"{HYUNDAI_IDP_BASE_URL}/authorize?{urlencode(params)}"


def exchange_code_for_token(code: str, *, timeout: float = 20.0) -> dict[str, Any]:
    """Exchange an authorization code for a Hyundai token payload."""

    response = requests.post(
        f"{HYUNDAI_IDP_BASE_URL}/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TOKEN_REDIRECT_URI,
            "client_id": TOKEN_CLIENT_ID,
            "client_secret": TOKEN_CLIENT_SECRET,
        },
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
            f"Token endpoint returned HTTP {response.status_code}: {payload}"
        )

    if "refresh_token" not in payload:
        raise BrowserReauthError(
            f"Token response does not contain refresh_token: {payload}"
        )

    return payload
