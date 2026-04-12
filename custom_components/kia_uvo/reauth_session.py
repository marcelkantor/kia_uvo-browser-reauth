"""Short-lived reauthentication sessions for the local token broker."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import secrets
from typing import Any

from aiohttp import web

from homeassistant.components import webhook
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.util import dt as dt_util

from .const import DATA_BROKER_REAUTH_MANAGER, DOMAIN

SESSION_TTL = timedelta(minutes=15)


@dataclass(slots=True)
class BrokerReauthSession:
    """Runtime-only broker session used during reauthentication."""

    flow_id: str
    entry_id: str
    webhook_id: str
    state: str
    created_at: Any
    expires_at: Any
    payload: dict[str, Any] | None = None
    used: bool = False
    broker_source: str | None = None
    last_error: str | None = None
    received_at: Any | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BrokerReauthSessionManager:
    """Manage short-lived webhook-backed broker sessions."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._sessions_by_flow: dict[str, BrokerReauthSession] = {}
        self._sessions_by_webhook: dict[str, BrokerReauthSession] = {}
        self._sessions_by_state: dict[str, BrokerReauthSession] = {}

    def _cleanup_expired(self) -> None:
        now = dt_util.utcnow()
        expired = [
            session
            for session in self._sessions_by_flow.values()
            if session.used or session.expires_at <= now
        ]
        for session in expired:
            self._remove_session(session)

    def _remove_session(self, session: BrokerReauthSession) -> None:
        webhook.async_unregister(self.hass, session.webhook_id)
        self._sessions_by_flow.pop(session.flow_id, None)
        self._sessions_by_webhook.pop(session.webhook_id, None)
        self._sessions_by_state.pop(session.state, None)

    async def async_create_session(
        self,
        *,
        flow_id: str,
        entry_id: str,
        username: str | None = None,
    ) -> BrokerReauthSession:
        """Create a one-time broker session and webhook."""

        self._cleanup_expired()

        old_session = self._sessions_by_flow.get(flow_id)
        if old_session is not None:
            self._remove_session(old_session)

        created_at = dt_util.utcnow()
        session = BrokerReauthSession(
            flow_id=flow_id,
            entry_id=entry_id,
            webhook_id=secrets.token_hex(24),
            state=secrets.token_urlsafe(24),
            created_at=created_at,
            expires_at=created_at + SESSION_TTL,
            metadata={"username": username or ""},
        )

        webhook.async_register(
            self.hass,
            DOMAIN,
            "Kia Uvo Browser Reauth",
            session.webhook_id,
            self._async_handle_webhook,
            allowed_methods=("POST",),
        )

        self._sessions_by_flow[flow_id] = session
        self._sessions_by_webhook[session.webhook_id] = session
        self._sessions_by_state[session.state] = session
        return session

    def async_get_by_flow(self, flow_id: str) -> BrokerReauthSession | None:
        """Get a session by config flow id."""

        self._cleanup_expired()
        return self._sessions_by_flow.get(flow_id)

    def async_get_by_state(self, state: str) -> BrokerReauthSession | None:
        """Get a session by one-time state."""

        self._cleanup_expired()
        return self._sessions_by_state.get(state)

    async def async_finish_session(self, session: BrokerReauthSession) -> None:
        """Mark a session as finished and unregister its webhook."""

        session.used = True
        self._remove_session(session)

    def async_webhook_url(self, session: BrokerReauthSession) -> str:
        """Build a webhook URL for the broker.

        We prefer an external URL when available because the broker commonly runs
        on a separate desktop and not necessarily inside the same network.
        """

        try:
            base_url = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            try:
                base_url = get_url(self.hass)
            except NoURLAvailableError:
                return f"/api/webhook/{session.webhook_id}"

        return f"{base_url}/api/webhook/{session.webhook_id}"

    def async_description_placeholders(
        self,
        session: BrokerReauthSession,
    ) -> dict[str, str]:
        """Return description placeholders for the reauth waiting step."""

        webhook_url = self.async_webhook_url(session)
        broker_command = (
            "python hyundai_token_broker.py "
            f'--state "{session.state}" '
            f'--webhook-url "{webhook_url}"'
        )
        expires_at = dt_util.as_local(session.expires_at).strftime("%Y-%m-%d %H:%M:%S")
        return {
            "state": session.state,
            "webhook_url": webhook_url,
            "expires_at": expires_at,
            "broker_command": broker_command,
        }

    async def _async_handle_webhook(
        self,
        hass: HomeAssistant,
        webhook_id: str,
        request: web.Request,
    ) -> web.Response:
        """Receive a token payload from the local broker."""

        self._cleanup_expired()
        session = self._sessions_by_webhook.get(webhook_id)
        if session is None:
            return web.json_response(
                {"status": "error", "reason": "session_not_found"},
                status=404,
            )

        if session.expires_at <= dt_util.utcnow():
            session.last_error = "session_expired"
            return web.json_response(
                {"status": "error", "reason": "session_expired"},
                status=410,
            )

        try:
            payload = await request.json()
        except ValueError:
            session.last_error = "invalid_json"
            return web.json_response(
                {"status": "error", "reason": "invalid_json"},
                status=400,
            )

        state = payload.get("state")
        token_payload = payload.get("token")
        if state != session.state:
            session.last_error = "invalid_state"
            return web.json_response(
                {"status": "error", "reason": "invalid_state"},
                status=400,
            )

        if not isinstance(token_payload, dict) or "refresh_token" not in token_payload:
            session.last_error = "invalid_payload"
            return web.json_response(
                {"status": "error", "reason": "invalid_payload"},
                status=400,
            )

        session.payload = payload
        session.received_at = dt_util.utcnow()
        session.broker_source = payload.get("source", {}).get("broker")

        await hass.config_entries.flow.async_configure(
            session.flow_id,
            {
                "reauth_session_state": session.state,
                "reauth_session_from_webhook": True,
            },
        )

        return web.json_response({"status": "ok"})


def async_get_session_manager(hass: HomeAssistant) -> BrokerReauthSessionManager:
    """Get or lazily create the broker reauth session manager."""

    domain_data = hass.data.setdefault(DOMAIN, {})
    manager = domain_data.get(DATA_BROKER_REAUTH_MANAGER)
    if manager is None:
        manager = BrokerReauthSessionManager(hass)
        domain_data[DATA_BROKER_REAUTH_MANAGER] = manager
    return manager
