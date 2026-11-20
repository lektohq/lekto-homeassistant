# Lekto for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) integration for the
[Lekto](https://github.com/lektohq/lekto) DMS. It talks to Lekto through its REST API with
[pylekto](https://github.com/lektohq/pylekto).

> [!NOTE]
> The integration is in beta: it reports the numbers of the household's documents, reacts to new
> documents, starts actions in Lekto and tells when a new release of Lekto is out.

The documentation is in [`docs/`](docs/README.md): [installation](docs/installation.md),
[setup](docs/setup.md), [sensors and update](docs/sensors.md), [document event](docs/events.md),
[actions](docs/actions.md), [use cases](docs/use-cases.md), [limitations](docs/limitations.md),
[troubleshooting](docs/troubleshooting.md), [diagnostics](docs/diagnostics.md),
[removal](docs/removal.md).

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
