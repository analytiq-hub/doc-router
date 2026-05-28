"""Registry entry that loads a Python node executor on first ``execute`` / ``poll`` / validation."""

from __future__ import annotations

from typing import Any

from analytiq_data.flows.builtin_manifest import BuiltinNodeSpec


class LazyBuiltinNode:
    """Palette metadata from ``node.manifest.json``; executor loaded on demand."""

    def __init__(self, spec: BuiltinNodeSpec, manifest: dict[str, Any]) -> None:
        self._spec = spec
        self._manifest = manifest
        self._delegate: Any = None

        self.key = str(manifest["key"])
        self.label = str(manifest["label"])
        self.description = str(manifest["description"])
        self.category = str(manifest["category"])
        self.is_trigger = bool(manifest["is_trigger"])
        self.is_merge = bool(manifest["is_merge"])
        self.min_inputs = int(manifest["min_inputs"])
        max_inputs = manifest.get("max_inputs")
        self.max_inputs = None if max_inputs is None else int(max_inputs)
        self.outputs = int(manifest["outputs"])
        self.output_labels = list(manifest.get("output_labels") or [])
        self.parameter_schema = manifest["parameter_schema"]
        self.icon_key = manifest.get("icon_key")
        self.credential_slots = list(manifest.get("credential_slots") or [])
        self.palette_group = manifest.get("palette_group")
        self.polling = bool(manifest.get("polling", False))
        self.experimental = bool(manifest.get("experimental", False))
        self.type_version = int(manifest.get("type_version", 1))
        if "batch_execute_inputs" in manifest:
            self.batch_execute_inputs = bool(manifest["batch_execute_inputs"])

    def _load(self) -> Any:
        if self._delegate is None:
            from analytiq_data.flows.builtin_loader import instantiate_builtin

            self._delegate = instantiate_builtin(self._spec)
        return self._delegate

    def validate_parameters(self, params: dict[str, Any]) -> list[str]:
        return self._load().validate_parameters(params)

    async def execute(
        self,
        context: Any,
        node: dict[str, Any],
        inputs: list[list[Any]],
    ) -> list[list[Any]]:
        return await self._load().execute(context, node, inputs)

    def __getattr__(self, name: str) -> Any:
        # Only for attributes not defined on this class (e.g. poll). A typo here
        # imports the full executor; prefer explicit methods for new entry points.
        return getattr(self._load(), name)
