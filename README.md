# Lekto for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) integration for the
[Lekto](https://github.com/lektohq/lekto) DMS. It talks to Lekto through its REST API with
[pylekto](https://github.com/lektohq/pylekto).

> [!NOTE]
> The integration is being built: it installs and loads, but does nothing yet.

## Requirements

- Home Assistant 2026.11 or newer
- A Lekto instance Home Assistant reaches, and a personal API token from it

## Installation

The integration is not in the Marketplace's catalog yet; add this repository to it yourself
(the Marketplace asks you to connect GitHub for that):

1. In Home Assistant, go to **Settings → Marketplace** and select **Add from link**.
2. Under **GitHub link**, enter `lektohq/lekto-homeassistant`, select the type **Integration** if
   asked, and select **Add**.
3. Open **Lekto** in the list and select **Install**.

## Removal

Open **Lekto** in the Marketplace and select **Uninstall** from its menu (⋮). While the
integration is still set up, the Marketplace offers **Delete and uninstall**.

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
