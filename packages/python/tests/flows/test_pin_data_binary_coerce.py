from __future__ import annotations

import analytiq_data as ad


def test_coerce_pin_data_node_output_supports_binary_refs() -> None:
    raw = {
        "main": [
            [
                {
                    "json": {"ok": True},
                    "binary": {
                        "pdf": {
                            "mime_type": "application/pdf",
                            "file_name": "a.pdf",
                            "storage_id": "flow_pins:pin/r1/n1/0/0/pdf/a.pdf",
                            "file_size": 3,
                        }
                    },
                    "meta": {},
                }
            ]
        ]
    }
    items = ad.flows.coerce_pin_data_node_output(raw)
    assert len(items) == 1
    assert items[0].json == {"ok": True}
    assert items[0].binary["pdf"].mime_type == "application/pdf"
    assert items[0].binary["pdf"].storage_id == "flow_pins:pin/r1/n1/0/0/pdf/a.pdf"

