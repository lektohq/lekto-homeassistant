# Actions

The integration offers actions for scripts and automations. Each names the Lekto instance it runs
on (`config_entry_id`) and needs rights of its own ([setup](setup.md)); an action whose rights the
token lacks fails and names them.

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
