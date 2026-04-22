def register_docrouter_nodes() -> None:
    """Register DocRouter nodes; import is deferred to avoid package init cycles."""

    from analytiq_data.docrouter_flows.register import register_docrouter_nodes as _register

    _register()


__all__ = ["register_docrouter_nodes"]
