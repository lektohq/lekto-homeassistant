# Setup

## The API token

Home Assistant uses an API token of a Lekto admin, made for it alone. In Lekto, go to
**Settings › API-Tokens**, create a token with **Eigene Rechte** and tick:

| Right | Why |
| --- | --- |
| `admin:count_all` | the numbers of the whole household, not only the admin's own documents |
| `documents:count` or `documents:read` | the numbers; `documents:read` includes `documents:count` |
| `system:read` | the state of Lekto's jobs, search index and classifier |

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

## A new token

When Lekto refuses the token (unknown, expired or revoked) or it lacks the rights above, for
example because its user is no admin anymore, Home Assistant asks for a new one: it reports
"Authentication expired for Lekto" under **Settings → System → Repairs**, and the entry under
**Settings → Devices & services** offers to enter a new token. Make one as above and enter it
there. It must come from the same Lekto instance; the address and the other settings stay.

## A new address

When Lekto moves to another address, or its certificate changes, open **Lekto** under
**Settings → Devices & services** and select **Reconfigure** from the entry's menu (⋮). Enter
the new URL and whether to verify the certificate; the token stays. The address must lead to the
same Lekto instance, and the token must still have the rights above there.
