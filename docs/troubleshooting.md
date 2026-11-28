# Troubleshooting

## Setting up fails

| Message | Cause and fix |
| --- | --- |
| Failed to connect to Lekto | Home Assistant cannot reach the address: check the URL (with `https://` or `http://` and the port), that Lekto runs, and the certificate; for a self-signed one, turn off **Verify SSL certificate** |
| Lekto does not accept the token | The token is unknown, expired or revoked: make a new one in Lekto |
| The token lacks rights | The token misses `documents:count` or `admin:count_all`; the token's user must be an active admin ([setup](setup.md#the-api-token)) |
| The server does not answer as Lekto 0.16 or newer does | The address leads to something else, or to an older Lekto: update Lekto |
| This Lekto instance is already set up | Each instance is set up once; to change its address, use **Reconfigure** on the existing entry |
| Lekto at this address is another instance than the one set up | When reconfiguring or entering a new token: the address or token belongs to another Lekto instance; use the one the entry was set up with, or remove the entry and add the other instance |
| Unexpected error | Something the integration did not expect; turn on the debug log (below) and report it |

## After setup

- **The sensors are unavailable.** Lekto does not answer; the log says why once, and again when
  it answers. They come back by themselves.
- **"Lekto: … off" under Repairs.** The token lost a right; see [a right gone](setup.md#a-right-gone).
- **"Lekto: update …" or "Lekto: unreadable API version" under Repairs.** Lekto and the
  integration speak different versions of the API; see
  [another version of Lekto's API](setup.md#another-version-of-lektos-api).
- **Home Assistant asks for a new token.** Lekto no longer accepts the token or it lost a required
  right; enter a new one ([a new token](setup.md#a-new-token)).
- **The entry fails with "another Lekto instance".** The address now leads to another instance:
  **Reconfigure** the entry with the right address.
- **The document event does not exist.** It needs `documents:read` and `admin:documents_all`
  ([setup](setup.md#the-api-token)).
- **The document event is unavailable.** The integration has no connection to Lekto's event
  stream; the log says "Lost the event stream" once, with the reason, and "The event stream is
  back" once it flows again. The integration connects again by itself: five seconds after a
  stream that flowed, after each try that fails twice as long, up to five minutes, and longer
  when Lekto asks it to. If it comes and goes, a firewall or proxy between Home Assistant and
  Lekto cuts long connections, or holds the stream back instead of passing it on as it comes.
- **An action fails with "lacks the rights".** Each action needs rights of its own
  ([actions](actions.md)); give them to a new token.

## Debug log

To see more of what the integration does, turn on debug logging: open **Lekto** under
**Settings → Devices & services** and select **Enable debug logging** from the entry's menu (⋮).
Reproduce the problem, then select **Disable debug logging**; Home Assistant offers the log as a
download. Attach it, with the [diagnostics](diagnostics.md), to a problem report on
[GitHub](https://github.com/lektohq/lekto-homeassistant/issues). Neither holds the token.
