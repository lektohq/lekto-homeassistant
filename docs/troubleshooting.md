# Troubleshooting

## Setting up fails

| Message | Cause and fix |
| --- | --- |
| Failed to connect to Lekto | Home Assistant cannot reach the address: check the URL (with `https://` or `http://` and the port), that Lekto runs, and the certificate; for a self-signed one, turn off **Verify SSL certificate** |
| Lekto does not accept the token | The token is unknown, expired or revoked: make a new one in Lekto |
| The token lacks rights | The token misses `documents:count` or `admin:count_all`; the token's user must be an active admin ([setup](setup.md#the-api-token)) |
| The server does not answer as Lekto 0.16 or newer does | The address leads to something else, or to an older Lekto: update Lekto |
| This Lekto instance is already set up | Each instance is set up once; to change its address or token, use **Reconfigure** or a new token on the existing entry |

## After setup

- **The sensors are unavailable.** Lekto does not answer; the log says why once, and again when
  it answers. They come back by themselves.
- **"Lekto: … off" under Repairs.** The token lost a right; see [a right gone](setup.md#a-right-gone).
- **"Lekto: update …" under Repairs.** Lekto and the integration speak different versions of the
  API; see [another version of Lekto's API](setup.md#another-version-of-lektos-api).
- **Home Assistant asks for a new token.** Lekto no longer accepts the token or it lost a required
  right; enter a new one ([a new token](setup.md#a-new-token)).
- **The entry fails with "another Lekto instance".** The address now leads to another instance:
  **Reconfigure** the entry with the right address.
- **The document event never fires.** It needs `documents:read` and `admin:documents_all`; without
  them it does not exist. A firewall or proxy that cuts long connections makes the integration
  connect again and again; it waits up to five minutes between tries.
- **An action fails with "lacks the rights".** Each action needs rights of its own
  ([actions](actions.md)); give them to a new token.

## Debug log

To see what the integration and pylekto do, turn on debug logging: open **Lekto** under
**Settings → Devices & services** and select **Enable debug logging** from the entry's menu (⋮).
Reproduce the problem, then select **Disable debug logging**; Home Assistant offers the log as a
download. Attach it, with the [diagnostics](diagnostics.md), to a problem report on
[GitHub](https://github.com/lektohq/lekto-homeassistant/issues). Neither holds the token.
