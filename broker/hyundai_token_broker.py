"""Local token broker for Hyundai Europe reauthentication.

This helper is meant to run on the user's desktop. It opens the Hyundai login
flow in Chrome, lets the user solve login and reCAPTCHA manually, captures the
authorization code from the final browser URL, exchanges it for a token, and
POSTs the token payload to a one-time Home Assistant webhook.

This is intentionally outside Home Assistant because the browser session and
reCAPTCHA are much more reliable on the local desktop than inside a server-side
environment.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import chromedriver_autoinstaller
import requests
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service


HYUNDAI_IDP_BASE_URL = "https://idpconnect-eu.hyundai.com/auth/api/v2/user/oauth2"
LOGIN_CLIENT_ID = "peuhyundaiidm-ctb"
LOGIN_REDIRECT_URI = "https://ctbapi.hyundai-europe.com/api/auth"
TOKEN_CLIENT_ID = "6d477c38-3ca4-4cf3-9557-2a1929a94654"
TOKEN_CLIENT_SECRET = "KUy49XxPzLpLuoK0xhBC77W6VXhmtQR9iQhmIFjjoY4IpxsV"
TOKEN_REDIRECT_URI = "https://prd.eu-ccapi.hyundai.com:8080/api/v1/user/oauth2/token"


def build_login_url(*, state: str, language: str, ui_locales: str) -> str:
    return (
        f"{HYUNDAI_IDP_BASE_URL}/authorize?"
        f"client_id={LOGIN_CLIENT_ID}&"
        f"redirect_uri={requests.utils.quote(LOGIN_REDIRECT_URI, safe='')}&"
        "nonce=&"
        f"state={requests.utils.quote(state, safe='')}&"
        "scope=openid+profile+email+phone&"
        "response_type=code&"
        f"connector_client_id={LOGIN_CLIENT_ID}&"
        "connector_scope=&"
        "connector_session_key=&"
        "country=&"
        "captcha=1&"
        f"ui_locales={requests.utils.quote(ui_locales, safe='')}&"
        f"lang={requests.utils.quote(language, safe='')}"
    )


def build_token_authorize_url(*, state: str, language: str) -> str:
    return (
        f"{HYUNDAI_IDP_BASE_URL}/authorize?"
        "response_type=code&"
        f"client_id={TOKEN_CLIENT_ID}&"
        f"redirect_uri={requests.utils.quote(TOKEN_REDIRECT_URI, safe='')}&"
        f"lang={requests.utils.quote(language, safe='')}&"
        f"state={requests.utils.quote(state, safe='')}"
    )


def exchange_code_for_token(code: str, *, timeout: float = 20.0) -> dict[str, Any]:
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
    payload = response.json()
    if response.status_code != 200:
        raise RuntimeError(
            f"OAuth token endpoint returned HTTP {response.status_code}: {payload}"
        )
    return payload


def _install_driver() -> str:
    try:
        _ = chromedriver_autoinstaller.get_chrome_version()
    except Exception as err:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "Google Chrome not found. Install Chrome on this machine first."
        ) from err

    return chromedriver_autoinstaller.install()


def _start_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("--window-size=1200,900")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36_CCS_APP_AOS"
    )

    driver_path = _install_driver()

    try:
        return webdriver.Chrome(service=Service(driver_path), options=options)
    except WebDriverException:
        driver_dir = Path(driver_path).parent
        if driver_dir.exists():
            shutil.rmtree(driver_dir, ignore_errors=True)
        driver_path = chromedriver_autoinstaller.install()
        return webdriver.Chrome(service=Service(driver_path), options=options)


def _write_debug_html(driver: webdriver.Chrome) -> Path:
    out_dir = Path.cwd()
    out_path = out_dir / f"hyundai_token_broker_debug_{int(time.time())}.html"
    out_path.write_text(driver.page_source, encoding="utf-8")
    return out_path


def _extract_code_from_url(url: str) -> str | None:
    match = re.search(r"[?&]code=([^&]+)", url)
    return match.group(1) if match else None


def run_broker(args: argparse.Namespace) -> int:
    print("=" * 70)
    print("HYUNDAI TOKEN BROKER")
    print("Complete Hyundai login and reCAPTCHA in the opened Chrome window.")
    print("=" * 70)

    driver = _start_driver()
    try:
        driver.get(
            build_login_url(
                state=args.state,
                language=args.language,
                ui_locales=args.ui_locales,
            )
        )

        input("\nPress ENTER after Hyundai login is complete...")

        driver.get(
            build_token_authorize_url(
                state=args.state,
                language=args.language,
            )
        )
        time.sleep(args.authorize_wait_seconds)

        current_url = driver.current_url
        code = _extract_code_from_url(current_url)
        if not code:
            debug_path = _write_debug_html(driver)
            print("ERROR: Authorization code not found in browser URL.")
            print(f"Current URL: {current_url}")
            print(f"Debug HTML saved to: {debug_path}")
            return 1

        token_payload = exchange_code_for_token(code)
        refresh_token = token_payload.get("refresh_token")
        access_token = token_payload.get("access_token")
        print("\nCaptured token successfully.")
        print(
            json.dumps(
                {
                    "has_refresh_token": bool(refresh_token),
                    "has_access_token": bool(access_token),
                    "state": args.state,
                },
                indent=2,
            )
        )

        body = {
            "state": args.state,
            "token": token_payload,
            "source": {
                "platform": platform.system(),
                "broker": "local_selenium",
            },
        }

        if args.webhook_url:
            response = requests.post(args.webhook_url, json=body, timeout=20)
            print(f"\nWebhook POST -> HTTP {response.status_code}")
            print(response.text[:500] if response.text else "(empty response)")
            response.raise_for_status()
        else:
            print("\nNo webhook URL provided, token was not sent to Home Assistant.")

        return 0
    finally:
        driver.quit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hyundai Europe token broker")
    parser.add_argument("--state", required=True, help="One-time reauth session state")
    parser.add_argument(
        "--webhook-url",
        help="One-time Home Assistant webhook URL that accepts the token payload",
    )
    parser.add_argument("--language", default="en")
    parser.add_argument("--ui-locales", default="en-US")
    parser.add_argument("--authorize-wait-seconds", type=float, default=2.0)
    return parser


if __name__ == "__main__":
    sys.exit(run_broker(build_parser().parse_args()))
