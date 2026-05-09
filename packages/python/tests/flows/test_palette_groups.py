from types import SimpleNamespace

from analytiq_data.flows import FlowsCodeNode, FlowsHttpRequestNode, FlowsManualTriggerNode
from analytiq_data.flows.palette_groups import normalize_palette_group, resolve_palette_group


def test_resolve_manual_trigger_palette_group_trigger():
    assert resolve_palette_group(FlowsManualTriggerNode()) == "trigger"


def test_resolve_code_palette_group_core():
    assert resolve_palette_group(FlowsCodeNode()) == "core"


def test_resolve_http_request_palette_group_core():
    assert resolve_palette_group(FlowsHttpRequestNode()) == "core"


def test_normalize_palette_group_unknown_returns_none():
    assert normalize_palette_group("nope") is None


def test_explicit_palette_group_class_attr():
    nt = SimpleNamespace(key="ext.notion", is_trigger=False, palette_group="flow")
    assert resolve_palette_group(nt) == "flow"
