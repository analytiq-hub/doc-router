"""
Generic flow engine (DocRouter-independent).

See `docs/flows.md` for the v1 spec and semantics.
"""

from .items import *
from .connections import *
from .context import *
from .execution import *
from .node_registry import *
from .expressions import *
from .engine import *
from .code_runner import *
from .nodes import *
from .register_builtin import *


def register_docrouter_nodes() -> None:
    """Register DocRouter nodes on the global engine registry (`docrouter_flows.register`)."""

    from analytiq_data.docrouter_flows.register import register_docrouter_nodes as _register

    _register()

