# Document event

The event entity **Document** (`event.lekto_document`) fires when a document of the household comes
in, is filed or waits for someone to look at it. It carries the document's id and, when a review is
needed, the lane; no title, contact or type, which stay in Lekto. It comes from Lekto's event stream
and stays available while the sensors' numbers cannot be fetched. It needs the rights
`documents:read` and `admin:documents_all` ([setup](setup.md)).

| Event type (`event_type`) | Shown as | When | Attributes |
| --- | --- | --- | --- |
| `received` | Received | A document came in | `document_id` |
| `filed` | Filed | A document was filed in its space | `document_id` |
| `review_required` | Review required | A document waits in the inbox | `document_id`, `lane`: `yellow` (review) or `red` (action needed) |

Lekto sends no events that happened while the integration was not connected; the sensors catch
up with the numbers.

## Example

A notification when a document needs action:

```yaml
automation:
  - alias: Lekto document needs action
    triggers:
      - trigger: state
        entity_id: event.lekto_document
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
