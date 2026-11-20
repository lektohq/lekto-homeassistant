# Actions

The integration offers actions for scripts and automations: upload a file, fetch the mailboxes,
count and list documents. Each names the Lekto instance it runs on (`config_entry_id`) and needs
rights of its own ([setup](setup.md)); an action whose rights the token lacks fails and names them.

## `lekto.upload`

Uploads a file from Home Assistant's media to Lekto, which processes it like any other document.

| Field | Required | Meaning |
| --- | --- | --- |
| `config_entry_id` | yes | The Lekto instance |
| `file` | yes | A PDF, a JPEG, PNG or TIFF image, or a mail (`.eml`) from Home Assistant's media, such as the folder `media` |
| `name` | no | The name Lekto keeps; the file's own name if empty. Without an extension it gets the file's |
| `space` | no | The name of the space the document goes to; the token user's personal space if empty. Needs `spaces:read` with `admin:documents_all` |

Needs `documents:upload`. The response holds `document_id` and `url`, the document in Lekto's web
interface. A file Lekto holds already fails the action with the id of the document it holds, if the
token may read that document.

```yaml
action: lekto.upload
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  file:
    media_content_id: media-source://media_source/local/scans/bill.pdf
    media_content_type: application/pdf
response_variable: uploaded
```

## `lekto.fetch_mail`

Has Lekto fetch its mailboxes now instead of at their next interval.

| Field | Required | Meaning |
| --- | --- | --- |
| `config_entry_id` | yes | The Lekto instance |
| `mailbox` | no | The name of one mailbox, active or not; every active mailbox if empty. A name two mailboxes share is refused |

Needs `system:read`, `system:write` and `admin:mailboxes`. The response lists the mailboxes asked
to fetch (`mailboxes`); Lekto fetches them in the background.

## Filters

`lekto.count` and `lekto.list_documents` take the same filters; a filter left empty takes all,
and several filters narrow each other. They cover the whole household.

| Field | Meaning |
| --- | --- |
| `inbox` | `true`: only documents open in the household's inbox, as the sensor **Inbox open** counts them (in processing, to review, action needed, or new and not yet seen by the token's user); `false`: only those not in it |
| `lane` | Only documents in these lanes: `green` (went through or was resolved; in the inbox such a document shows as new), `yellow` (review), `red` (action needed), `processing` |
| `contact` | Only documents of these contacts, by name; needs `master_data:read` |
| `document_type` | Only documents of these types, by name; needs `master_data:read` |
| `tag` | Only documents with any of these tags, by name; needs `master_data:read` |
| `space` | Only documents in these spaces, by name; needs `spaces:read` with `admin:documents_all` |
| `date_from`, `date_to` | Only documents dated within these days |

Names are compared without regard to case; a name several contacts share takes all of them, a
name Lekto does not know fails the action.

## `lekto.count`

Counts the household's documents that match the filters. Needs only the rights every token has.
The response holds `count`.

```yaml
action: lekto.count
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  lane: [red]
  document_type: Invoice
response_variable: invoices
```

## `lekto.list_documents`

Lists the household's documents that match the filters, newest first by when they came into Lekto;
`date` is the document's own date, which the date filters use. Needs `documents:read` and
`admin:documents_all`.

| Field | Meaning |
| --- | --- |
| `limit` | How many documents at most, 1 to 50; 10 if empty |
| `fields` | What each document carries beside `id`, `title`, `date` and `url`: `lane` (empty while Lekto processes the document), `contact`, `document_type`, `tags` (these three need `master_data:read`), `space` (needs `spaces:read` with `admin:documents_all`) |

The response holds `documents`, newest first. A name is empty when the token lacks its right or
Lekto cannot give it at the moment; a filter by name fails then.

```yaml
action: lekto.list_documents
data:
  config_entry_id: 0123456789abcdef0123456789abcdef
  lane: [red, yellow]
  limit: 3
  fields: [contact]
response_variable: waiting
```
