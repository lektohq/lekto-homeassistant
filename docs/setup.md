# Setup

## The API token

Home Assistant uses an API token of a Lekto admin, made for it alone. In Lekto, go to
**Settings › API-Tokens**, create a token with **Eigene Rechte** and tick at least:

| Right | Why |
| --- | --- |
| `documents:count` | the numbers of the inbox and of all documents |
| `admin:count_all` | those numbers for the whole household, not only the admin's own documents |

The integration refuses a token without them. Every other right is optional: the integration
reads the token's rights when it sets up and offers what they allow.

| Optional right | What it opens |
| --- | --- |
| `system:read` | the diagnostic sensors: jobs, search index, classifier |
| `documents:read` and `admin:documents_all` | Lekto's events: the document event, and the numbers updated as soon as something changes; `admin:documents_all` lets the token read every document of the household; and the action that lists documents |
| `master_data:read` | the names of contacts, document types and tags: in the document event's fields, and the actions' filters and listed fields |
| `spaces:read` (with `admin:documents_all`) | the names of spaces: in the document event's fields, the space of an upload, and the actions' filters and listed fields |
| `documents:upload` | the action that uploads a file ([actions](actions.md)) |
| `system:read`, `system:write` and `admin:mailboxes` | the action that fetches the mailboxes now |

`documents:read` includes `documents:count`. Lekto shows the token only once; copy it.
[Lekto's documentation of API tokens](https://github.com/lektohq/lekto/blob/main/docs/api-tokens.md)
suggests rights for Home Assistant; that list lacks `admin:documents_all`, which the events need.

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

When Lekto refuses the token (unknown, expired or revoked) or it lacks `documents:count` or
`admin:count_all`, for example because its user is no admin anymore, Home Assistant asks for a
new one: it reports "Authentication expired for Lekto" under **Settings → System → Repairs**,
and the entry under **Settings → Devices & services** offers to enter a new token. Make one as
above and enter it there. It must come from the same Lekto instance; the address and the other
settings stay.

## A right gone

When the token loses an optional right, the integration sets itself up again without what that
right opened, and reports it under **Settings → System → Repairs**, for example "Lekto:
diagnostic sensors off". The repair offers two ways out:

- **Enter a new token** that has the right again; the entities come back.
- **Remove the entities** that the right opened. The repair does not come back; a later token
  with the right brings them back.

## A new address

When Lekto moves to another address, or its certificate changes, open **Lekto** under
**Settings → Devices & services** and select **Reconfigure** from the entry's menu (⋮). Enter
the new URL and whether to verify the certificate; the token stays. The address must lead to the
same Lekto instance, and the token must still have the rights above there.

## Options

**Configure** on the entry picks the fields the document event carries beside the document's id:
title, date, contact, document type, tags, space ([document event](events.md#fields)). None is
picked at first.
