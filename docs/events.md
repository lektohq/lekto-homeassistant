# Document event

The event entity **Document** (`event.lekto_document`) fires when a document of the household comes
in, is filed or waits for someone to look at it. It carries the document's id and, when a review is
needed, the lane; no title, contact or type, which stay in Lekto. It needs the rights
`documents:read` and `admin:documents_all` ([setup](setup.md)).

The events come on a connection of their own, Lekto's event stream. While the integration has no
such connection, the entity is unavailable; it is back as soon as the stream flows again, before
the next event. The sensors' numbers have no part in this: while they cannot be fetched, events
still come.

An automation should skip a change from `unavailable`, which is the entity coming back, and no
other: the state is unknown until the first event, and again after Home Assistant restarted or
the entry was set up again while the stream was lost, so the next event changes it from unknown.

| Event type (`event_type`) | Shown as | When | Attributes |
| --- | --- | --- | --- |
| `received` | Received | A document came in | `document_id` |
| `filed` | Filed | A document was filed in its space | `document_id` |
| `review_required` | Review required | A document waits in the inbox | `document_id`, `lane`: `yellow` (review) or `red` (action needed) |

Lekto sends no events that happened while the integration was not connected; the sensors catch
up with the numbers.

## Fields

The event carries only the document's id unless you pick more: under **Settings → Devices &
services**, open **Lekto** and select **Configure**. With any field picked, the integration asks
Lekto once per event for the document; the names of contacts, types, tags and spaces it keeps and
fetches at most hourly. The fields stay out of the recorder, so no title or name ends up in Home
Assistant's history; automations still see them, and the last event, with its fields, is kept across
restarts.

| Field (attribute) | Value | Needs |
| --- | --- | --- |
| `title` | The document's title | |
| `document_date` | Its date, such as `2026-11-03` | |
| `contact` | The contact's name | `master_data:read` |
| `document_type` | The document type's name | `master_data:read` |
| `tags` | The names of its tags, as a list | `master_data:read` |
| `space` | The name of its space | `spaces:read` (with `admin:documents_all`) |

The options offer only the fields the token's rights allow, and nothing without the rights of
the document event. A field Lekto cannot give at the
moment, or a document without a date or contact, is left out.

## Example

A notification when a document needs action:

```yaml
automation:
  - alias: Lekto document needs action
    triggers:
      - trigger: state
        entity_id: event.lekto_document
        # After a restart or a lost connection the last event is back; it is no new one.
        not_from: unavailable
    conditions:
      - condition: state
        entity_id: event.lekto_document
        attribute: event_type
        state: review_required
      - condition: state
        entity_id: event.lekto_document
        attribute: lane
        state: red
    actions:
      - action: notify.notify
        data:
          message: A document in Lekto needs action.
```
