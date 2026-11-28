"""The quality scale: what Home Assistant's hassfest checks only for integrations in its core.

hassfest skips ``quality_scale.yaml`` and the checks of its rules for a custom integration, so the
tier in ``manifest.json`` is the integration's own word. These tests hold what hassfest would
check; the rules it checks through a flow or a setup are held by the tests of those.
"""

import ast
import json
from importlib import metadata
from pathlib import Path

import pytest
from homeassistant.util.yaml import load_yaml_dict

from custom_components.lekto import PLATFORMS

INTEGRATION = Path(__file__).parent.parent / "custom_components" / "lekto"

# hassfest asks for each rule of its ALL_RULES (Home Assistant 2026.11); a release may add some.
RULES = {
    "action-exceptions",
    "action-setup",
    "appropriate-polling",
    "async-dependency",
    "brands",
    "common-modules",
    "config-entry-unloading",
    "config-flow",
    "config-flow-test-coverage",
    "dependency-transparency",
    "devices",
    "diagnostics",
    "discovery",
    "discovery-update-info",
    "docs-actions",
    "docs-conditions",
    "docs-configuration-parameters",
    "docs-data-update",
    "docs-examples",
    "docs-high-level-description",
    "docs-installation-instructions",
    "docs-installation-parameters",
    "docs-known-limitations",
    "docs-removal-instructions",
    "docs-supported-devices",
    "docs-supported-functions",
    "docs-triggers",
    "docs-troubleshooting",
    "docs-use-cases",
    "dynamic-devices",
    "entity-category",
    "entity-device-class",
    "entity-disabled-by-default",
    "entity-event-setup",
    "entity-translations",
    "entity-unavailable",
    "entity-unique-id",
    "exception-translations",
    "has-entity-name",
    "icon-translations",
    "inject-websession",
    "integration-owner",
    "log-when-unavailable",
    "parallel-updates",
    "reauthentication-flow",
    "reconfiguration-flow",
    "repair-issues",
    "runtime-data",
    "stale-devices",
    "strict-typing",
    "test-before-configure",
    "test-before-setup",
    "test-coverage",
    "unique-config-entry",
}

# The functions hassfest looks at, with the position of the entry; the integration has some.
ENTRY_FUNCTIONS = {
    "__init__": {
        "async_migrate_entry": 1,
        "async_remove_config_entry_device": 1,
        "async_remove_entry": 1,
        "async_setup_entry": 1,
        "async_unload_entry": 1,
    },
    "diagnostics": {"async_get_config_entry_diagnostics": 1, "async_get_device_diagnostics": 1},
    "config_flow": {"async_get_options_flow": 0},
    **{str(platform): {"async_setup_entry": 1} for platform in PLATFORMS},
}


def _functions(module: str) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse((INTEGRATION / f"{module}.py").read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def test_every_rule_done_or_exempt() -> None:
    """The file names every rule, and the tier of the manifest has none open below it."""
    rules = load_yaml_dict(str(INTEGRATION / "quality_scale.yaml"))["rules"]
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    undone = [
        name
        for name, state in rules.items()
        if state != "done"
        and not (isinstance(state, dict) and state.get("status") == "exempt" and state["comment"])
    ]

    assert set(rules) == RULES
    assert manifest["quality_scale"] == "platinum"
    assert not undone


@pytest.mark.parametrize("module", ENTRY_FUNCTIONS)
def test_entry_parameter_typed(module: str) -> None:
    """Each function Home Assistant hands the entry to takes it as ``LektoConfigEntry``."""
    functions = _functions(module)
    taking = {name: at for name, at in ENTRY_FUNCTIONS[module].items() if name in functions}

    assert taking
    for name, position in taking.items():
        annotation = functions[name].args.args[position].annotation
        assert isinstance(annotation, ast.Name), name
        assert annotation.id == "LektoConfigEntry", name


def test_config_entry_named_once() -> None:
    """Only the alias ``LektoConfigEntry`` names Home Assistant's ``ConfigEntry``."""
    users = {
        path.name
        for path in INTEGRATION.glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if (isinstance(node, ast.Name) and node.id == "ConfigEntry")
        or (isinstance(node, ast.Attribute) and node.attr == "ConfigEntry")
    }

    assert users == {"coordinator.py"}


def test_requirements_typed() -> None:
    """Every library the integration requires ships its types (PEP 561)."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    untyped = [
        requirement
        for requirement in manifest["requirements"]
        if not any(
            file.name == "py.typed"
            for file in metadata.distribution(requirement.split("==")[0]).files or []
        )
    ]

    assert not untyped
