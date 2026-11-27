import asyncio
import json

import pytest

from fivewhys.desk.openai_planner import OpenAIPlanner
from fivewhys.desk.mcp_tools import INPUTS, validate_plan


def test_real_api_shape_to_validated_mcp_plan(monkeypatch):
    responses = []
    def post(self, payload):
        responses.append(payload)
        return {"status":"completed", "id":"resp_test", "model":"test-snapshot",
                "usage":{"input_tokens":100,"output_tokens":60},
                "output":[{"type":"function_call","name":name, "call_id":"call_"+name,
                           "arguments":json.dumps(args)} for name,args in [
                              ("search_logs",{"query":"HikariPool"}),
                              ("search_past_incidents",{"query":"pool"}),
                              ("list_change_events",{})]]}
    monkeypatch.setenv("OPENAI_API_KEY","fixture")
    monkeypatch.setattr(OpenAIPlanner,"_post",post)
    planner = OpenAIPlanner()
    specs = [{"name":k,"description":k,"inputSchema":v.model_json_schema()} for k,v in INPUTS.items()]
    plan = asyncio.run(planner("주문 장애 원인을 조사해 줘", specs))
    assert len(validate_plan(plan)) == 3
    assert planner.last_usage["backend"] == "OpenAI Responses API"
    assert responses[0]["store"] is False
    assert set(x["name"] for x in responses[0]["tools"]) == set(INPUTS)
    assert len(planner.last_usage["call_ids"]) == 3


def test_partial_response_rejected(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","fixture")
    monkeypatch.setattr(OpenAIPlanner,"_post",lambda self,payload: {"status":"incomplete"})
    with pytest.raises(ValueError):
        asyncio.run(OpenAIPlanner()("주문 장애", []))


@pytest.mark.parametrize("value", ["fixture", "  fixture\n", "OPENAI_API_KEY='fixture'", "Bearer fixture"])
def test_accepts_pasted_env_assignment(monkeypatch, value):
    from fivewhys.desk.openai_planner import secret_value
    monkeypatch.setenv("OPENAI_API_KEY", value)
    assert secret_value() == "fixture"


def test_error_classification_returns_only_fixed_label():
    from fivewhys.desk.openai_planner import classify_error
    assert classify_error({"message":"Missing scopes: api.responses.write"}) == "missing_permissions"
    assert classify_error({"code":"unrecognized", "message":"private detail"}) == "provider_rejection_unspecified"
