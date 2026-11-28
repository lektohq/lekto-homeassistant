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

# Where Home Assistant hands over the config entry, and at which position.
ENTRY_PARAMETERS = [
    ("__init__", "async_setup_entry", 1),
    ("__init__", "async_unload_entry", 1),
    ("diagnostics", "async_get_config_entry_diagnostics", 1),
    ("config_flow", "async_get_options_flow", 0),
    *((str(platform), "async_setup_entry", 1) for platform in PLATFORMS),
]


def _module(name: str) -> ast.Module:
    return ast.parse((INTEGRATION / f"{name}.py").read_text(encoding="utf-8"))


def test_every_rule_done_or_exempt() -> None:
    """The tier in the manifest stands only while no rule is open; an exemption says why."""
    rules = load_yaml_dict(str(INTEGRATION / "quality_scale.yaml"))["rules"]

    undone = [
        name
        for name, state in rules.items()
        if state != "done"
        and not (isinstance(state, dict) and state.get("status") == "exempt" and state["comment"])
    ]

    assert not undone


@pytest.mark.parametrize(("module", "function", "position"), ENTRY_PARAMETERS)
def test_entry_parameter_typed(module: str, function: str, position: int) -> None:
    """Each function Home Assistant hands the entry to takes it as ``LektoConfigEntry``."""
    functions = [
        node
        for node in ast.walk(_module(module))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == function
    ]

    assert len(functions) == 1
    annotation = functions[0].args.args[position].annotation
    assert isinstance(annotation, ast.Name)
    assert annotation.id == "LektoConfigEntry"


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
