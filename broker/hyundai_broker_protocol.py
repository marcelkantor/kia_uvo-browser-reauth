"""Protocol handler for hyundai-broker:// URLs on Windows."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import parse_qs, urlparse

from hyundai_token_broker import run_broker


def _single(params: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
    values = params.get(key)
    if not values:
        return default
    return values[0]


def namespace_from_protocol_url(url: str) -> argparse.Namespace:
    parsed = urlparse(url)
    if parsed.scheme != "hyundai-broker":
        raise ValueError(f"Unsupported scheme: {parsed.scheme}")

    action = parsed.netloc or parsed.path.lstrip("/")
    if action != "launch":
        raise ValueError(f"Unsupported hyundai-broker action: {action}")

    params = parse_qs(parsed.query, keep_blank_values=True)
    state = _single(params, "state")
    webhook_url = _single(params, "webhook_url")
    if not state or not webhook_url:
        raise ValueError("Protocol URL must include state and webhook_url")

    return argparse.Namespace(
        state=state,
        webhook_url=webhook_url,
        language=_single(params, "language", "en"),
        ui_locales=_single(params, "ui_locales", "en-US"),
        authorize_wait_seconds=float(_single(params, "authorize_wait_seconds", "2.0")),
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: hyundai_broker_protocol.py hyundai-broker://launch?...")  # noqa: T201
        return 1

    try:
        namespace = namespace_from_protocol_url(args[0])
    except Exception as err:  # pragma: no cover - input validation
        print(f"ERROR: {err}")  # noqa: T201
        return 1

    return run_broker(namespace)


if __name__ == "__main__":
    sys.exit(main())
