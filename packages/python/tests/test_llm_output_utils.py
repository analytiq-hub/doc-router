import json

from analytiq_data.llm.llm_output_utils import extract_json_from_resp_content, process_llm_resp_content


def test_extract_json_from_resp_content_empty_string():
    assert extract_json_from_resp_content("") == ""


def test_extract_json_from_resp_content_strips_redacted_thinking():
    raw = (
        '<think>Let me reason about this...</think>'
        '{"answer": 42}'
    )
    cleaned = extract_json_from_resp_content(raw)
    assert json.loads(cleaned) == {"answer": 42}


def test_extract_json_from_resp_content_generic_fence():
    raw = '```\n{"status": "ok"}\n```'
    cleaned = extract_json_from_resp_content(raw)
    assert json.loads(cleaned) == {"status": "ok"}


def test_extract_json_from_resp_content_embedded_json_fence():
    raw = 'Here is the result:\n```json\n{"field": "value"}\n```\nThanks!'
    cleaned = extract_json_from_resp_content(raw)
    assert json.loads(cleaned) == {"field": "value"}


def test_extract_json_from_resp_content_outermost_object_fallback():
    raw = 'The extracted data is {"a": 1, "b": {"c": 2}} as requested.'
    cleaned = extract_json_from_resp_content(raw)
    assert json.loads(cleaned) == {"a": 1, "b": {"c": 2}}


def test_process_llm_resp_content_strips_json_fence_for_openai():
    raw = '```json\n{"first_name": "David", "last_name": "Kim"}\n```'
    cleaned = process_llm_resp_content(raw, "openai")
    assert json.loads(cleaned) == {"first_name": "David", "last_name": "Kim"}


def test_process_llm_resp_content_bare_json_unchanged():
    raw = '{"status": "ok"}'
    cleaned = process_llm_resp_content(raw, "openai")
    assert json.loads(cleaned) == {"status": "ok"}


def test_process_llm_resp_content_groq_regression_with_thinking_block():
    """Groq previously used the aggressive cleanup path; confirm universal path still works."""
    raw = (
        '<think>step by step</think>'
        '```json\n{"vendor": "Acme"}\n```'
    )
    cleaned = process_llm_resp_content(raw, "groq")
    assert json.loads(cleaned) == {"vendor": "Acme"}


def test_extract_json_from_resp_content_unclosed_fence():
    raw = '```json\n{"field": "value"}'
    cleaned = extract_json_from_resp_content(raw)
    assert json.loads(cleaned) == {"field": "value"}
