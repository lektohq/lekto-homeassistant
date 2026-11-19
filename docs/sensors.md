# Sensors

The integration adds one device, **Lekto**, for the instance. Its sensors count the documents of
every user of the household, not only those of the token's user. They are fetched every 60
seconds; while Lekto does not answer, they are unavailable.

| Sensor | Value |
| --- | --- |
| **Inbox open** | Documents open in the inbox: every tab but done |
| **Inbox new** | New documents nobody has looked at |
| **Inbox review** | Documents to review |
| **Inbox action needed** | Documents that need someone to act |
| **Inbox processing** | Documents Lekto is still processing |
| **Inbox worst lane** | The worst lane among the open documents: **Action needed** before **Review** before **New**; unknown while no open document waits outside processing |
| **Documents** | All documents |

A lane that a newer Lekto knows and this version of the integration does not shows as unknown.
