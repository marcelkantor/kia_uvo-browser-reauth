# Token broker concept

## Why the broker matters

For Hyundai Europe, the fragile part is not token storage in Home Assistant.
The fragile part is obtaining a fresh token while respecting Hyundai's browser
login flow and fixed redirect expectations.

The broker solves exactly that.

## Proposed model

### Home Assistant side

1. User starts `Re-authenticate` from the integration UI.
2. The integration creates a short-lived reauth session:
   - `entry_id`
   - `state`
   - one-time webhook id
   - expiration time
3. Home Assistant shows instructions or a launch link for the local broker.

### Broker side

1. Broker starts on the user's desktop.
2. Broker opens Chrome with the Hyundai login URL.
3. User logs in and solves reCAPTCHA manually.
4. Broker requests the token authorize URL.
5. Broker extracts the authorization code from the browser URL.
6. Broker exchanges the code for a token.
7. Broker POSTs the token payload to the one-time Home Assistant webhook.

### Finish

1. Home Assistant validates the session state.
2. Home Assistant stores the new token in the config entry.
3. Home Assistant reloads the integration.

## Why this is stronger than a pure HA callback

- no need for Home Assistant to own Hyundai's expected redirect URI
- browser and reCAPTCHA stay on the user's actual desktop
- Home Assistant remains the source of truth for the config entry
- the integration UI can still stay native and clean

## Security posture

- no password storage required
- webhook should be one-time and short-lived
- broker should POST only to the specific webhook created for the reauth session
- broker payload should include the expected `state`
- Home Assistant should reject expired or already-used sessions

## MVP checklist

### Broker MVP

- start Chrome
- let user log in manually
- capture code
- exchange token
- send webhook payload to HA

### Integration MVP

- create reauth session
- expose webhook endpoint
- validate `state`
- update config entry token
- reload entry
