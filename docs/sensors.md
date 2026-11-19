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

## Diagnostic sensors

They show how Lekto itself is doing, and stand under **Diagnostic** on the device. The two
marked *off* start disabled; enable them on the device if you need them. Lekto runs without a
search index or a classifier, or while one of them fails: their sensor is unavailable then, the
others go on.

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
