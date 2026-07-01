"""Sanity-check API request models (field descriptions wired to correct attributes)."""


def test_run_flow_request_field_descriptions() -> None:
    from app.routes.flows import RunFlowRequest

    st = RunFlowRequest.model_fields["start_trigger_node_id"].description or ""
    assert "multiple triggers" in st.lower()

    tn = RunFlowRequest.model_fields["target_node_id"].description or ""
    assert "execute" in tn.lower() or "upstream" in tn.lower()
