"""
Generic flow engine (DocRouter-independent).

See `docs/flows.md` for the v1 spec and semantics.
"""

from .items import *
from .connections import *
from .port_types import *
from .context import *
from .execution import *
from .node_registry import *
from .expressions import *
from .node_name import *
from .errors import execution_error_envelope, node_error_envelope
from .trace import append_trace, pop_node_trace, trace_http, trace_http_on_debug, trace_http_on_success
from .org_log_level import (
    DEFAULT_FLOW_LOG_LEVEL,
    fetch_org_flow_log_level,
    flow_log_level_includes,
    normalize_flow_log_level,
)
from .flow_settings import (
    FLOW_TIMEZONE_DEFAULT,
    INSTANCE_DEFAULT_TIMEZONE,
    normalize_flow_settings,
    resolve_flow_timezone,
    validate_flow_settings,
)
from .node_settings import (
    FLOW_NODE_BATCH_SIZE_DEFAULT,
    FLOW_NODE_BATCH_SIZE_MAX,
    FLOW_NODE_BATCH_SIZE_MIN,
    resolve_node_batch_size,
    validate_node_batch_size,
)
from .item_batch import map_flow_items_batch
from .engine import *
from .recovery import *
from .resume import *
from .seed_validation import (
    RunDataSeedValidationError,
    finalized_dirty_node_ids,
    validate_and_filter_run_data_seed,
)
from .code_runner import *
from .credentials import *
from .credential_inject import *
from .credential_kind_registry import *
from .credential_runtime import *
from .register_builtin import *
from .triggers import *
from .url_ssrf_guard import *
from . import webhook_parse
from . import webhook_params


def __getattr__(name: str):
    from analytiq_data.flows.builtin_manifest import BUILTIN_CLASS_NAMES

    if name in BUILTIN_CLASS_NAMES:
        from analytiq_data.flows import nodes

        return getattr(nodes, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    from analytiq_data.flows.builtin_manifest import BUILTIN_CLASS_NAMES

    return sorted(set(globals()) | BUILTIN_CLASS_NAMES)


def register_docrouter_nodes() -> None:
    """Register DocRouter nodes on the global engine registry (`docrouter_flows.register`)."""

    from analytiq_data.docrouter_flows.register import register_docrouter_nodes as _register

    _register()

