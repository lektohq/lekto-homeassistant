<img src="custom_components/lekto/brand/icon.png" alt="Lekto" width="96" align="right">

# Lekto for Home Assistant

[![Marketplace: custom repository](https://img.shields.io/badge/Marketplace-custom%20repository-41BDF5.svg)](#installation)
[![Release](https://img.shields.io/github/v/release/lektohq/lekto-homeassistant)](https://github.com/lektohq/lekto-homeassistant/releases)
[![Quality scale: Platinum](https://img.shields.io/badge/quality%20scale-platinum-E5E4E2.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
[![License: MIT](https://img.shields.io/github/license/lektohq/lekto-homeassistant)](LICENSE)

Brings [Lekto](https://github.com/lektohq/lekto), the self-hosted document management system,
into Home Assistant. See how many documents wait in the inbox, react to new documents in
automations, upload scans to Lekto and know when a new release of Lekto is out. The integration
talks to Lekto's REST API in the local network through
[pylekto](https://github.com/lektohq/pylekto); nothing leaves it.

> [!NOTE]
> The integration is in beta, as is Lekto. It meets every rule of Home Assistant's
> [quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
> up to Platinum.

## Features

- **Sensors** for the household's inbox and documents, updated every 60 seconds and at once
  when Lekto reports a change
- **Diagnostic sensors** for Lekto itself: health, jobs, search index, classifier
- **Document event** when a document comes in, is filed or needs a look, for automations
- **Actions**: upload a file, fetch the mailboxes now, count and list documents
- **Update entity** that shows when a new release of Lekto is out
- **Repairs** when the token loses a right or Lekto and the integration speak different API
  versions

## Requirements

- Home Assistant 2026.11 or newer
- Lekto 0.17 (its API 0.3), reachable from Home Assistant
- An admin account in Lekto, to make the API token

## Installation

> [!IMPORTANT]
> Lekto is not in the Marketplace's catalog: searching the Marketplace does not find it. Add this
> repository to your Marketplace as a custom repository first; the Marketplace asks you to connect
> GitHub for that.

1. In Home Assistant, go to **Settings → Marketplace** and select **Add from link**.
2. Under **GitHub link**, enter `lektohq/lekto-homeassistant`, select the type **Integration** if
   asked, and select **Add**.
3. Open **Lekto** in the list, select **Install** and restart Home Assistant.

The Marketplace then offers new releases of the integration like those of any other.

## Configuration

### 1. Create an API token in Lekto

In Lekto, go to **Settings › API-Tokens** and create a token with **Eigene Rechte** for Home
Assistant alone. Lekto shows the token only once; copy it.

Two rights are required; the integration refuses a token without them:

| Right | Why |
| --- | --- |
| `documents:count` | the numbers of the inbox and of all documents |
| `admin:count_all` | those numbers for the whole household, not only the admin's own documents |

Every other right is optional. The integration reads the token's rights when it sets up and
offers what they allow:

| Optional right | What it opens |
| --- | --- |
| `system:read` | the diagnostic sensors and the update entity |
| `documents:read` and `admin:documents_all` | the document event, instant updates of the numbers, the action that lists documents |
| `master_data:read` | names of contacts, document types and tags in the event and the actions |
| `spaces:read` (with `admin:documents_all`) | names of spaces in the event and the actions |
| `documents:upload` | the action that uploads a file |
| `system:read`, `system:write` and `admin:mailboxes` | the action that fetches the mailboxes |

### 2. Add the integration

Go to **Settings → Devices & services**, select **Add integration** and choose **Lekto**.

| Parameter | Meaning |
| --- | --- |
| **URL** | The address of Lekto's web interface, such as `https://lekto.example.com` |
| **API token** | The token from step 1 (`lekto_…`) |
| **Verify SSL certificate** | On by default; turn it off only for a self-signed certificate |

**Configure** on the entry picks the fields the document event carries beside the document's id:
title, date, contact, document type, tags, space.

## Entities

The integration adds one device, **Lekto**. The sensors count the documents of every user of the
household.

### Sensors

| Sensor | Value |
| --- | --- |
| **Inbox open** | Documents open in the inbox: every tab but done |
| **Inbox new** | New documents nobody has looked at |
| **Inbox review** | Documents to review |
| **Inbox action needed** | Documents that need someone to act |
| **Inbox processing** | Documents Lekto is still processing |
| **Inbox worst lane** | The worst lane among the open documents: **Action needed**, **Review** or **New** |
| **Documents** | All documents |

### Diagnostic sensors

**Health** needs no right; the others need `system:read`. Those marked *off* start disabled.

| Sensor | Value |
| --- | --- |
| **Health** | **OK**, **Degraded** or **Down** |
| **Jobs failed** | Jobs the worker gave up |
| **Jobs waiting** | Jobs that wait for a worker |
| **Worker last started** (*off*) | When a worker last took a job |
| **Search index waiting** | Jobs of the search index that wait |
| **Confirmations since training** (*off*) | Documents confirmed since the classifier was last trained |

### Event and update

| Entity | What it does | Needs |
| --- | --- | --- |
| **Document** (`event.lekto_document`) | Fires `received`, `filed` or `review_required` with the document's id and, if picked, its fields | `documents:read`, `admin:documents_all` |
| **Lekto** (update) | The version Lekto runs and its newest release; install it where Lekto runs | `system:read` |

## Actions

| Action | What it does | Needs |
| --- | --- | --- |
| `lekto.upload` | Uploads a file from Home Assistant's media to Lekto | `documents:upload` |
| `lekto.fetch_mail` | Has Lekto fetch its mailboxes now | `system:read`, `system:write`, `admin:mailboxes` |
| `lekto.count` | Counts the documents that match filters (inbox, lane, contact, type, tag, space, dates) | the required rights |
| `lekto.list_documents` | Lists the newest documents that match the same filters | `documents:read`, `admin:documents_all` |

## Example

A notification when a document needs action:

```yaml
automation:
  - alias: Lekto document needs action
    triggers:
      - trigger: state
        entity_id: event.lekto_document
        not_from: [unavailable, unknown]
    conditions:
      - condition: state
        entity_id: event.lekto_document
        attribute: lane
        state: red
    actions:
      - action: notify.notify
        data:
          message: A document in Lekto needs action.
```

More in the [use cases](docs/use-cases.md).

## Documentation

The full documentation is in [`docs/`](docs/README.md): [installation](docs/installation.md),
[setup](docs/setup.md), [sensors and update](docs/sensors.md), [document event](docs/events.md),
[actions](docs/actions.md), [use cases](docs/use-cases.md), [supported versions](docs/supported.md),
[limitations](docs/limitations.md), [troubleshooting](docs/troubleshooting.md),
[diagnostics](docs/diagnostics.md), [removal](docs/removal.md).

## Development

Open the repository in its devcontainer (`.devcontainer/`); it runs `script/setup`, which
installs the dependencies and the Git hooks. Outside the devcontainer, `script/setup` creates a
local `.venv` first.

```sh
uv sync
uv run prek run --all-files   # every check: Ruff, mypy, pytest with coverage, typos, yamllint
script/develop                # Home Assistant with the integration on http://localhost:8123
```

## License

MIT, see [LICENSE](LICENSE).
