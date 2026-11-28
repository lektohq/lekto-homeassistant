# Use cases and examples

What a household does with Lekto in Home Assistant, and an automation for each. The entity ids are
those of the first instance (a second one gets `_2`); the `config_entry_id` of an action is the id
of your entry (in the action editor, pick the instance and switch to YAML to see it).

## Know when the inbox needs you

The sensor **Inbox worst lane** turns `red` when a document needs someone to act, such as a bill
Lekto could not read. Show it on a dashboard, or be told:

```yaml
automation:
  - alias: Lekto inbox needs action
    triggers:
      - trigger: state
        entity_id: sensor.lekto_inbox_worst_lane
        to: red
        not_from: [unavailable, unknown]
    actions:
      - action: notify.notify
        data:
          message: >-
            {{ states('sensor.lekto_inbox_action_needed') }} documents in Lekto need action.
```

## Hear about new documents

The [document event](events.md) fires when a document comes in. With the field `title` picked
in the options:

```yaml
automation:
  - alias: Lekto new document
    triggers:
      - trigger: state
        entity_id: event.lekto_document
        # After a restart or a lost connection the last event is back; it is no new one.
        not_from: [unavailable, unknown]
    conditions:
      - condition: state
        entity_id: event.lekto_document
        attribute: event_type
        state: received
    actions:
      - action: notify.notify
        data:
          message: >-
            New in Lekto: {{ state_attr('event.lekto_document', 'title') or 'a document' }}.
```

## Send a scan to Lekto

A scanner that saves into Home Assistant's media folder `scans` can hand a file to Lekto with the
action [`lekto.upload`](actions.md#lektoupload) (needs `documents:upload`), for example from a
script that gets the file's name:

```yaml
script:
  lekto_upload_scan:
    fields:
      name:
        description: The file's name in the folder scans
    sequence:
      - action: lekto.upload
        data:
          config_entry_id: 0123456789abcdef0123456789abcdef
          file:
            media_content_id: "media-source://media_source/local/scans/{{ name }}"
            media_content_type: application/pdf
```

## Fetch the mail when it matters

Lekto fetches its mailboxes at an interval. To fetch now, for example when you come home:

```yaml
automation:
  - alias: Lekto fetch mail on arrival
    triggers:
      - trigger: state
        entity_id: person.alex
        to: home
    actions:
      - action: lekto.fetch_mail
        data:
          config_entry_id: 0123456789abcdef0123456789abcdef
```

## Ask what waits

[`lekto.count`](actions.md#lektocount) and
[`lekto.list_documents`](actions.md#lektolist_documents) answer questions such as "how many
invoices need action" or "what are the three newest documents in the inbox", for a voice assistant
or a morning summary:

```yaml
script:
  lekto_morning_summary:
    sequence:
      - action: lekto.list_documents
        data:
          config_entry_id: 0123456789abcdef0123456789abcdef
          inbox: true
          limit: 3
        response_variable: waiting
      - action: notify.notify
        data:
          message: >-
            {{ waiting.documents | map(attribute='title') | join(', ')
               or 'Nothing waits in Lekto.' }}
```

## Keep Lekto healthy

The diagnostic sensors **Health**, **Jobs failed** and **Jobs waiting** tell when Lekto itself has
trouble, and the [update entity](sensors.md#update) when a new release is out. **Health** is
`down` when Lekto answers but a service it needs failed, and unavailable when Lekto does not
answer at all:

```yaml
automation:
  - alias: Lekto not healthy
    triggers:
      - trigger: state
        entity_id: sensor.lekto_health
        to: [down, unavailable]
        for: "00:10:00"
    actions:
      - action: notify.notify
        data:
          message: Lekto has been down or unreachable for ten minutes.
```
