# Use cases and examples

What a household does with Lekto in Home Assistant, and an automation for each. The entity ids are
those of an instance set up under the name **Lekto**; the `config_entry_id` of an action is the id
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

A scanner that saves into Home Assistant's media folder `scans` hands each new file to Lekto with
the action [`lekto.upload`](actions.md#lektoupload), for example from a script the scanner's
button starts:

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
invoices need action" or "what are the three newest documents to review", for a voice assistant
or a morning summary:

```yaml
script:
  lekto_morning_summary:
    sequence:
      - action: lekto.list_documents
        data:
          config_entry_id: 0123456789abcdef0123456789abcdef
          lane: [red, yellow]
          limit: 3
        response_variable: waiting
      - action: notify.notify
        data:
          message: >-
            {% for document in waiting.documents %}{{ document.title }}
            {% else %}Nothing waits in Lekto.{% endfor %}
```

## Keep Lekto healthy

The diagnostic sensors **Health**, **Jobs failed** and **Jobs waiting** tell when Lekto itself has
trouble, and the [update entity](sensors.md#update) when a new release is out:

```yaml
automation:
  - alias: Lekto not healthy
    triggers:
      - trigger: state
        entity_id: sensor.lekto_health
        to: down
        for: "00:10:00"
    actions:
      - action: notify.notify
        data:
          message: Lekto has been down for ten minutes.
```
