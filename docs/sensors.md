# Sensors

The integration adds one device, **Lekto**, for the instance. Its sensors count the documents of
every user of the household, not only those of the token's user. They are fetched every 60 seconds;
while Lekto does not answer, they are unavailable. With the rights of Lekto's events
(`documents:read` and `admin:documents_all`, see [setup](setup.md)) they are also fetched at once
when Lekto reports that a document came in, was filed, needs a look, changed its lane, was
confirmed, moved or deleted. The integration then listens to Lekto's events all the time and
connects again when the connection drops, waiting a little longer after each quick failure, up to
five minutes; it then fetches the numbers again, as Lekto does not send the events it missed.

| Sensor | Value |
| --- | --- |
| **Inbox open** | Documents open in the inbox: every tab but done |
| **Inbox new** | New documents nobody has looked at |
| **Inbox review** | Documents to review |
| **Inbox action needed** | Documents that need someone to act |
| **Inbox processing** | Documents Lekto is still processing |
| **Inbox worst lane** | The worst lane among the open documents: **Action needed** before **Review** before **New**; unknown while no open document waits outside processing |
| **Documents** | All documents |

## Diagnostic sensors

They show how Lekto itself is doing, and stand under **Diagnostic** on the device. **Health** needs
no right; the others need `system:read` ([setup](setup.md)). The two marked *off* start disabled;
enable them on the device if you need them. Lekto runs without a search index or a classifier, or
while one of them fails: their sensor is unavailable then, the others go on.

| Sensor | Value |
| --- | --- |
| **Health** | **OK**, **Degraded** (an optional service failed, Lekto still works) or **Down** (a service Lekto needs failed, such as its object store) |
| **Jobs failed** | Jobs the worker gave up, within Lekto's retention period |
| **Jobs waiting** | Jobs whose time has come and that wait for a worker |
| **Worker last started** (*off*) | When a worker last took a job; long ago while jobs wait means no worker runs |
| **Search index waiting** | Jobs of the search index that wait, now or for later |
| **Confirmations since training** (*off*) | Documents confirmed since the classifier was last trained |

A lane or a health that a newer Lekto knows and this version of the integration does not shows
as unknown.

## Update

With `system:read` the device also has an update entity, **Lekto**, under **Diagnostic**. It shows
the version Lekto runs and the newest release, with a link to its release notes. Lekto looks for
its releases itself, once an hour; the integration reads what Lekto found, every 60 seconds. While
Lekto does not look (`LEKTO_UPDATE_CHECK` off) or has not looked yet, the newest release is
unknown. Home Assistant cannot install it: update Lekto where it runs, for example by pulling its
new image. Once Lekto runs another version, the integration sets itself up again, and the device
shows the new version.
