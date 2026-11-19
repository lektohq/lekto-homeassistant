# Lekto for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) integration for the
[Lekto](https://github.com/lektohq/lekto) DMS. It talks to Lekto through its REST API with
[pylekto](https://github.com/lektohq/pylekto).

> [!NOTE]
> The integration is being built: it sets up a Lekto instance, but has no entities yet.

The documentation is in [`docs/`](docs/README.md): [installation](docs/installation.md),
[setup](docs/setup.md), [removal](docs/removal.md).

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
