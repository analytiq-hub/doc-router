"""Manifest of builtin flow node types (Phase B lazy registration)."""

from __future__ import annotations

from typing import NamedTuple


class BuiltinNodeSpec(NamedTuple):
    key: str
    module: str
    class_name: str


BUILTIN_NODES: tuple[BuiltinNodeSpec, ...] = (
    BuiltinNodeSpec(
        "flows.trigger.manual",
        "analytiq_data.flows.nodes.trigger_manual",
        "FlowsManualTriggerNode",
    ),
    BuiltinNodeSpec(
        "flows.trigger.schedule",
        "analytiq_data.flows.nodes.trigger_schedule",
        "FlowsScheduleTriggerNode",
    ),
    BuiltinNodeSpec(
        "flows.trigger.webhook",
        "analytiq_data.flows.nodes.trigger_webhook",
        "FlowsWebhookTriggerNode",
    ),
    BuiltinNodeSpec(
        "flows.respond_to_webhook",
        "analytiq_data.flows.nodes.respond_to_webhook",
        "FlowsRespondToWebhookNode",
    ),
    BuiltinNodeSpec(
        "flows.http_request",
        "analytiq_data.flows.nodes.http_request",
        "FlowsHttpRequestNode",
    ),
    BuiltinNodeSpec(
        "flows.branch",
        "analytiq_data.flows.nodes.branch",
        "FlowsBranchNode",
    ),
    BuiltinNodeSpec(
        "flows.merge",
        "analytiq_data.flows.nodes.merge",
        "FlowsMergeNode",
    ),
    BuiltinNodeSpec(
        "flows.code",
        "analytiq_data.flows.nodes.code",
        "FlowsCodeNode",
    ),
    BuiltinNodeSpec(
        "flows.google_drive",
        "analytiq_data.flows.nodes.google_drive.node",
        "FlowsGoogleDriveNode",
    ),
    BuiltinNodeSpec(
        "flows.trigger.google_drive",
        "analytiq_data.flows.nodes.google_drive.trigger",
        "FlowsGoogleDriveTriggerNode",
    ),
    BuiltinNodeSpec(
        "flows.gmail",
        "analytiq_data.flows.nodes.gmail.node",
        "FlowsGmailNode",
    ),
    BuiltinNodeSpec(
        "flows.trigger.gmail",
        "analytiq_data.flows.nodes.gmail.trigger",
        "FlowsGmailTriggerNode",
    ),
    BuiltinNodeSpec(
        "flows.microsoft_onedrive",
        "analytiq_data.flows.nodes.microsoft_onedrive.node",
        "FlowsMicrosoftOneDriveNode",
    ),
    BuiltinNodeSpec(
        "flows.trigger.microsoft_onedrive",
        "analytiq_data.flows.nodes.microsoft_onedrive.trigger",
        "FlowsMicrosoftOneDriveTriggerNode",
    ),
)

SPEC_BY_KEY: dict[str, BuiltinNodeSpec] = {s.key: s for s in BUILTIN_NODES}
SPEC_BY_CLASS_NAME: dict[str, BuiltinNodeSpec] = {s.class_name: s for s in BUILTIN_NODES}
BUILTIN_CLASS_NAMES: frozenset[str] = frozenset(SPEC_BY_CLASS_NAME)
