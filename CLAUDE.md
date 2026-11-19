# CLAUDE.md

lekto-homeassistant is the Home Assistant integration (domain `lekto`) of Lekto DMS
(`lektohq/lekto`), a custom integration installed through Home Assistant's Marketplace. It talks
to Lekto only through pylekto (`lektohq/pylekto`). Python 3.14 only, Home Assistant 2026.11 or
newer. The repository is decided in `.knowledge/decisions/2026-11-19-homeassistant-repo.md`.

## Layout

| Path | Content |
| --- | --- |
| `custom_components/lekto/` | The integration: `manifest.json` (version `0.0.0`, set from the tag on release), `__init__.py`, `const.py`, `brand/` (the owl as icon) |
| `hacs.json` | What the Marketplace reads: name, Home Assistant from 2026.11.0, a release as `lekto.zip` |
| `tests/` | pytest with the fixtures of `pytest-homeassistant` (`hass`, `MockConfigEntry`, …); `tests/ruff.toml` adjusts the rules for tests |
| `config/` | The Home Assistant of `script/develop`: only `configuration.yaml` is in git |
| `script/` | `setup` (once: dependencies, Git hooks), `bootstrap` (every start of the devcontainer: dependencies), `develop` (Home Assistant with the integration on port 8123) |
| `.devcontainer/`, `Dockerfile.dev` | Devcontainer: Python 3.14, uv, gh, Claude Code; the virtual environment lives in `/home/vscode/.local/dev-venv` |
| `.github/` | Workflows (`ci.yml`, `release.yml`, Release Drafter, labels, stale, lock), labels, templates, `scripts/` (the test of the action pins) |
| `.knowledge/` | The knowledge in German as small notes with frontmatter; start with `INDEX.md` and `README.md`. A checkout of the private repository `lektohq/lekto-knowledge`, shared with lekto and pylekto and ignored by this one (see "Working style") |

## Commands

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run pytest                    # with coverage; fails below 95 %
uv run typos
uv run yamllint .
uv run prek run --all-files      # every hook at once, as before each commit
python3 -m unittest discover -s .github/scripts   # every action is pinned to a commit
script/develop                   # Home Assistant with the integration on http://localhost:8123
```

Run all checks before every commit; `script/setup` installs them as a Git hook (`prek install`).
CI also runs hassfest, Home Assistant's own check of the integration, from its image
`ghcr.io/home-assistant/hassfest` of the release the tests run against.

Publishing a release on GitHub runs `.github/workflows/release.yml`: it sets the version from the
tag in `manifest.json`, packs `custom_components/lekto` as `lekto.zip` and attaches it to the
release, which the Marketplace downloads (`hacs.json`: `zip_release`). The repository carries the
version `0.0.0`. Every action in a workflow is pinned to its commit with the version in a comment
(`uses: actions/checkout@<sha> # v7.0.1`, which Renovate updates); a test in `.github/scripts`
fails on a tag.

## Rules

- The integration talks to Lekto only through pylekto; no HTTP of its own. `manifest.json` pins
  pylekto exactly (`pylekto==0.1.0`), as Home Assistant requires; Renovate raises it.
- Home Assistant comes with `pytest-homeassistant`, one package per Home Assistant release, which
  pins `homeassistant` exactly; Renovate raises it together with the image of hassfest.
- The integration aims at the highest tier of Home Assistant's quality scale (Platinum);
  `quality_scale.yaml` holds the state of every rule.
- Not in the Marketplace's catalog (`hacs/default`) and no `hacs/action` in CI until Tobi says so
  (`.knowledge/open/homeassistant-default-catalog.md`); users add the repository themselves.
- Ruff (`select = ["ALL"]`) and mypy (`strict`) report nothing on new or changed code.
- No suppressions (`# noqa`, `# type: ignore` and the like): fix the cause. Only `# noqa: F401` on
  a re-export in an `__init__.py` is allowed without asking.
- Dependencies in `pyproject.toml` state lower bounds only; `uv.lock` pins the development
  environment. New dependencies need agreement first.
- This repository will be public: every value in code, tests, fixtures, commits and pull requests
  is made up. No real names, companies, IBANs, addresses, numbers, hosts or tokens.
- Comments explain *why* (constraints, surprises, workarounds), never *what*; one short line or
  none. No section or divider comments.
- Keep try clauses minimal: wrap only the statement that can raise, catch only the expected
  exceptions. An `@asynccontextmanager` always uses `try`/`finally`.
- Docstrings: a one-line summary, Google-style `Args:` where it helps; private `_` symbols one or
  two lines on *why* only. No `Example::` blocks.

## Labels

Every pull request carries exactly one category label from `.github/labels.yml` (`new-feature`,
`bugfix`, `enhancement`, `refactor`, `performance`, `maintenance`, `ci`, `documentation`,
`dependencies`, `dev-deps`, `breaking-change`); a check fails without one, and the Release Drafter
builds the release notes from them. Renovate (`renovate.json`, the hosted app) labels its own:
`dependencies` (pylekto in `manifest.json`), `dev-deps` (development dependencies, Home Assistant
and hassfest, the devcontainer, prek's hooks), `ci` (actions); it suggests a version 10 days after
its release at the earliest.
The version bump follows the labels (`breaking-change` or `major`: major; `new-feature` or
`minor`: minor; else patch). Tobi publishes and tags the release from the draft.
A pull request a user notices fills the section `## Release notes` of its description with one
sentence on what changes for them; it stands under the title in the release notes.

## Language

Code, comments, commit messages and documentation (README, docstrings) are English. The notes in
`.knowledge/` are German.

## Working style

- Plan first: read the notes in `.knowledge/` (`INDEX.md` first, area `homeassistant`), propose a
  plan, wait for approval.
- Decisions, plans, open points, working rules and history live only in the private repository
  `lektohq/lekto-knowledge`, checked out at `.knowledge/` (after a fresh clone:
  `git clone https://github.com/lektohq/lekto-knowledge.git .knowledge`). lekto and pylekto have
  their own checkouts of it: `git pull` before working, and commit and push every change straight to
  its `main` (`uv run tools/index.py` checks the notes and writes the index); nothing stays only
  local, and none of it goes into this repository. Notes about this integration carry the area
  `homeassistant` and their `code:` paths the prefix `lekto-homeassistant/`. Docstrings point at
  notes as `.knowledge/<folder>/<name>.md`.
- If something is unclear or a decision is missing, ask before implementing. Do not deviate from
  the decisions in `.knowledge/decisions/` on your own.
- Small, thematically separate commits. Keep answers short and precise.
