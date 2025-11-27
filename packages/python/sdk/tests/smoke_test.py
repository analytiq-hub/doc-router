import importlib
import pkgutil


def main() -> None:
    sdk = importlib.import_module("docrouter_sdk")
    from docrouter_sdk import DocRouterClient
    from docrouter_sdk.models.document import ListDocumentsResponse  # noqa: F401

    client = DocRouterClient(base_url="http://example")

    # Verify sub-APIs are present
    assert hasattr(client, "documents"), "missing documents API"
    assert hasattr(client, "ocr"), "missing ocr API"
    assert hasattr(client, "llm"), "missing llm API"
    assert hasattr(client, "schemas"), "missing schemas API"
    assert hasattr(client, "prompts"), "missing prompts API"
    assert hasattr(client, "tags"), "missing tags API"

    # Verify typing marker is packaged
    assert pkgutil.get_data("docrouter_sdk", "py.typed") is not None, "py.typed missing"

    print("SDK smoke test OK", getattr(sdk, "__version__", "no __version__"))


if __name__ == "__main__":
    main()


