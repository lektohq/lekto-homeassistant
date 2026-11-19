# Setup

## The API token

Home Assistant uses an API token of a Lekto admin, made for it alone. In Lekto, go to
**Settings › API-Tokens**, create a token with **Eigene Rechte** and tick:

| Right | Why |
| --- | --- |
| `admin:count_all` | the numbers of the whole household, not only the admin's own documents |
| `documents:count` or `documents:read` | the numbers; `documents:read` includes `documents:count` |

The integration refuses a token without them. Lekto shows the token only once; copy it.

[Lekto's documentation of API tokens](https://github.com/lektohq/lekto/blob/main/docs/api-tokens.md)
lists the rights of a token for everything the integration will do: `documents:read`,
`documents:upload`, `webhooks:read`, `webhooks:write`, `system:read`, `system:write`,
`admin:count_all`, `admin:mailboxes`, `admin:private_webhooks`.

## Adding the integration

Go to **Settings → Devices & services**, select **Add integration** and choose **Lekto**.

| Parameter | Meaning |
| --- | --- |
| **URL** | The address of Lekto's web interface, such as `https://lekto.example.com` |
| **API token** | The token from above (`lekto_…`) |
| **Verify SSL certificate** | On by default; turn it off only for a self-signed certificate |

The integration connects to Lekto and checks the token's rights before it saves the entry. Each
Lekto instance can be set up once; a second entry for the same instance is refused, whatever its
token.
