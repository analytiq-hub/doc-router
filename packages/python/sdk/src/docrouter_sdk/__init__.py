from .client import DocRouterClient

try:
    from importlib.metadata import version, PackageNotFoundError
    try:
        __version__ = version("docrouter-sdk")
    except PackageNotFoundError:
        __version__ = "0.0.0"
except Exception:
    __version__ = "0.0.0"

__all__ = ["DocRouterClient", "__version__"]