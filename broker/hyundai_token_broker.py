"""Local token broker for Europe reauthentication.

This helper is meant to run on the user's desktop. It opens the brand-specific
login flow in Chrome, lets the user solve login and reCAPTCHA manually, captures the
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
from custom_components.kia_uvo.browser_reauth import (
    brand_requires_secondary_authorize,
    build_login_url,
    build_token_authorize_url,
    exchange_code_for_token,
    get_brand_config,
    normalize_brand,
)


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
    brand = normalize_brand(getattr(args, "brand", None))
    config = get_brand_config(brand)
    print("=" * 70)
    print(f"{brand.upper()} TOKEN BROKER")
    print(
        f"Complete the {brand.capitalize()} login and reCAPTCHA in the opened Chrome window."
    )
    print("=" * 70)

    driver = _start_driver()
    try:
        driver.get(
            build_login_url(
                brand=brand,
                state=args.state,
                language=args.language,
                ui_locales=args.ui_locales,
            )
        )

        input(f"\nPress ENTER after {brand.capitalize()} login is complete...")

        if brand_requires_secondary_authorize(brand):
            driver.get(
                build_token_authorize_url(
                    brand=brand,
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

        token_payload = exchange_code_for_token(code, brand=brand)
        refresh_token = token_payload.get("refresh_token")
        access_token = token_payload.get("access_token")
        print("\nCaptured token successfully.")
        print(
            json.dumps(
                {
                    "brand": config.brand_key,
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
                "brand": config.brand_key,
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
    parser = argparse.ArgumentParser(description="Hyundai / Kia Europe token broker")
    parser.add_argument("--state", required=True, help="One-time reauth session state")
    parser.add_argument(
        "--webhook-url",
        help="One-time Home Assistant webhook URL that accepts the token payload",
    )
    parser.add_argument("--brand", default="hyundai")
    parser.add_argument("--language", default="en")
    parser.add_argument("--ui-locales", default="en-US")
    parser.add_argument("--authorize-wait-seconds", type=float, default=2.0)
    return parser


if __name__ == "__main__":
    sys.exit(run_broker(build_parser().parse_args()))
