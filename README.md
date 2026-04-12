# kia_uvo-browser-reauth

Experimental fork of `kia_uvo` focused on making Hyundai Bluelink / Kia Uvo
reauthentication feel native inside Home Assistant.

## Goal

The long-term goal is to replace the current "external token script" workflow
with a Home Assistant driven reauthentication flow:

1. User opens `Re-authenticate` in the integration.
2. Home Assistant starts a browser-oriented login flow.
3. User completes Hyundai login and reCAPTCHA.
4. A broker component exchanges the returned authorization code for a fresh
   token.
5. Home Assistant stores the token in the config entry and reloads the
   integration.

## Why this repo exists

The upstream integration already has:

- `config_flow`
- `reauth`
- token persistence in the config entry
- coordinator reload logic

What is still missing is a browser-friendly token renewal flow for Hyundai
Europe / Kia Europe.

## Important architectural note

This problem is harder than a typical Home Assistant OAuth callback.

In Hyundai Europe, the observed authorization flow is tied to a fixed
`redirect_uri` controlled by Hyundai. Earlier testing showed that exchanging
the code with a different redirect URI causes the token endpoint to reject the
request with a redirect mismatch error.

That means:

- a pure "redirect back directly to Home Assistant" approach is unlikely to be
  enough on its own
- a companion token broker may be required for a production-quality solution

This repository documents that limitation explicitly and starts the refactor by
extracting reusable browser-reauth helpers.

## Current contents

- upstream-derived `custom_components/kia_uvo`
- `browser_reauth.py`
  - Hyundai login URL builders
  - code-to-token exchange helper
- `token_store.py`
  - helper for updating a config entry with a new token
- `broker/hyundai_token_broker.py`
  - local desktop helper that opens the Hyundai login flow
  - captures the final authorization code
  - exchanges it for a token
  - posts the token to a Home Assistant webhook
- `broker/HyundaiTokenBroker.bat`
  - Windows wrapper for the broker script
- architecture notes in `docs/ARCHITECTURE.md`
- broker notes in `docs/BROKER.md`

## Status

This is an experimental foundation, not a finished release.

Current MVP progress:

- local broker implemented
- short-lived broker session manager implemented
- one-time webhook receiver implemented
- `reauth` flow extended with a broker waiting step for Hyundai/Kia Europe

Not yet completed:

- end-to-end tested install inside a real Home Assistant custom integration
- polished launch UX from inside the HA reauth dialog
- packaged desktop distribution of the broker

The next implementation milestone is:

1. wire the local broker into Home Assistant `reauth`
2. register and validate a one-time webhook/session in the integration
3. keep the UX centered around the integration's native `Re-authenticate`
   action

## Upstream and license

This work is based on `Hyundai-Kia-Connect/kia_uvo` and remains under the MIT
license. See `LICENSE`.
