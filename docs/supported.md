# Supported versions and functions

## Lekto

The integration works with Lekto 0.16 or newer, whose API speaks version 0.2. While Lekto is in
beta, every change of its API raises that version, and each release of the integration speaks
exactly one: after an update of Lekto, update the integration too. When the two do not fit, the
integration still runs and says what to update ([setup](setup.md#another-version-of-lektos-api)).
The integration needs only Lekto's address and an API token.

One entry is one Lekto instance and gets one device, **Lekto**. Several instances need an entry
each, with a token each.

## Functions

| What | Where | Needs |
| --- | --- | --- |
| Sensors: the inbox's numbers, its worst lane, all documents | [Sensors](sensors.md) | the required rights |
| Diagnostic sensors: health, jobs, search index, classifier | [Sensors](sensors.md#diagnostic-sensors) | `system:read` (health: none) |
| Update entity: the newest release of Lekto | [Sensors](sensors.md#update) | `system:read` |
| Document event: received, filed, review required, with chosen fields | [Document event](events.md) | `documents:read`, `admin:documents_all` |
| Actions: upload, fetch the mailboxes, count, list documents | [Actions](actions.md) | each its own |
| Repairs: a right gone, another version of the API | [Setup](setup.md#a-right-gone) | |
| Diagnostics for a problem report | [Diagnostics](diagnostics.md) | |

The [setup](setup.md#the-api-token) lists every right and what it opens.
