from __future__ import annotations

import json

import pytest

from analytiq_data.flows.content_ref import ContentRefError, resolve_content_refs


def test_bare_ref_replaces_with_text(tmp_path):
    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "a.txt").write_text("hello", encoding="utf-8")
    spec = {"body": {"$content_ref": "templates/a.txt"}}
    got = resolve_content_refs(spec, tmp_path)
    assert got == {"body": "hello"}


def test_bare_ref_json_object(tmp_path):
    (tmp_path / "data.json").write_text(json.dumps({"z": 1}), encoding="utf-8")
    spec = {"payload": {"$content_ref": "data.json"}}
    got = resolve_content_refs(spec, tmp_path)
    assert got == {"payload": {"z": 1}}


def test_bare_ref_keep_jinja_body_as_string(tmp_path):
    (tmp_path / "templates").mkdir()
    tpl = '{"channel": "{{ parameters.channel }}"}\n'
    (tmp_path / "templates" / "post.tpl").write_text(tpl, encoding="utf-8")
    spec = {
        "body": {
            "$content_ref": "templates/post.tpl",
            "$content_media_type": "application/json",
        }
    }
    got = resolve_content_refs(spec, tmp_path)
    assert isinstance(got["body"], str)
    assert "{{" in got["body"]
    assert got["body"] == tpl


def test_nested_ref_inside_loaded_json(tmp_path):
    (tmp_path / "inner.json").write_text('"x"', encoding="utf-8")
    outer = {"$content_ref": "outer.json"}
    (tmp_path / "outer.json").write_text(
        json.dumps({"a": {"$content_ref": "inner.json"}}),
        encoding="utf-8",
    )
    got = resolve_content_refs(outer, tmp_path)
    assert got == {"a": "x"}


def test_schema_string_default(tmp_path):
    (tmp_path / "snippet.py").write_text("print(1)", encoding="utf-8")
    schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "$content_ref": "snippet.py"},
        },
    }
    got = resolve_content_refs(schema, tmp_path)
    assert got["properties"]["code"] == {
        "type": "string",
        "default": "print(1)",
    }


def test_schema_object_default(tmp_path):
    blob = {"k": True}
    (tmp_path / "defaults.json").write_text(json.dumps(blob), encoding="utf-8")
    schema = {"type": "object", "$content_ref": "defaults.json"}
    got = resolve_content_refs(schema, tmp_path)
    assert got["type"] == "object"
    assert got["default"] == blob


def test_rejects_traversal(tmp_path):
    spec = {"x": {"$content_ref": "../etc/passwd"}}
    with pytest.raises(ContentRefError, match=r"\.\."):
        resolve_content_refs(spec, tmp_path)


def test_package_root_must_exist(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(ContentRefError, match="not a directory"):
        resolve_content_refs({}, missing)
