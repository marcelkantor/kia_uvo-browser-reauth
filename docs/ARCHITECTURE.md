# Architecture notes

## Product direction

The desired UX is:

1. Home Assistant user opens `Re-authenticate` from the integration.
2. Home Assistant launches a guided browser login flow.
3. User completes Hyundai login and reCAPTCHA.
4. The resulting authorization code is exchanged for a fresh refresh token.
5. Home Assistant updates the config entry and reloads `kia_uvo`.

## Constraint discovered during research

The Hyundai Europe token flow currently observed in the field works like this:

1. Browser login is initiated with Hyundai's login client.
2. Once the session is authenticated, a second authorize request is made for
   the token client.
3. The token endpoint accepts the code only when it is paired with Hyundai's
   expected `redirect_uri`.

In testing, using a different redirect URI produced a token error equivalent
to:

`Mismatched token redirect uri`

## Consequence

A direct Home Assistant callback may not be sufficient for Hyundai Europe.

The likely production path is:

- `kia_uvo` remains the Home Assistant integration and source of truth
- a broker component handles the browser session and code capture
- Home Assistant receives the final token payload from the broker

## Why still start in the integration repo

Even if a broker is needed, the integration is still the right home for:

- user-facing reauth flow
- config entry updates
- token persistence
- reload behavior
- future service/entity hooks for reauth

## Current repo scope

This repository currently focuses on the reusable foundation:

- URL builders for Hyundai login / authorize endpoints
- token exchange helper
- config entry token update helper

## Proposed phases

### Phase 1

- prepare an experimental fork
- extract browser reauth primitives
- document the redirect URI limitation

### Phase 2

- choose broker execution model
  - Home Assistant add-on
  - local desktop helper
  - browser automation sidecar

### Phase 3

- integrate broker with `config_flow` reauth
- expose a polished `Re-authenticate` experience in the integration UI

### Phase 4

- harden security model
- write docs and tests
- evaluate upstream contribution path
