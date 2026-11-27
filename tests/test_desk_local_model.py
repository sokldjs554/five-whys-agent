import asyncio

import pytest

from fivewhys.desk.local_model import LocalModelError, LocalPlanner, MODEL, TOOLS


SPECS = [{"name": name, "description": name} for name in TOOLS]


def completion(content):
    return {
        "id": "test-response",
        "model": MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_local_plan_prioritizes_selected_evidence_and_clears_failed_usage(monkeypatch):
    planner = LocalPlanner(version="v1")
    response = completion(
        '{"first_tool":"list_change_events","log_query":"timeout","report_query":"pool"}'
    )
    monkeypatch.setattr(planner, "_post", lambda payload: response)

    async def run():
        calls = await planner("Check deploys first, then pool timeouts", SPECS)
        assert calls == [
            {"tool": "list_change_events", "input": {}},
            {"tool": "search_logs", "input": {"query": "timeout", "limit": 5}},
            {"tool": "search_past_incidents", "input": {"query": "pool", "k": 4}},
        ]
        assert planner.last_usage["request_id"] == "test-response"
        response["choices"][0]["finish_reason"] = "length"
        with pytest.raises(LocalModelError):
            await planner("Check deploys first", SPECS)
        assert planner.last_usage == {}

    asyncio.run(run())


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        "broken",
        '{"first_tool":"write_to_database"}',
        '{"first_tool":"search_logs","log_query":" ","report_query":"pool"}',
    ],
)
def test_malformed_model_result_stops_before_tool_execution(monkeypatch, content):
    planner = LocalPlanner()
    monkeypatch.setattr(planner, "_post", lambda payload: completion(content))
    with pytest.raises(LocalModelError):
        asyncio.run(planner("pool", SPECS))


@pytest.mark.parametrize(
    "question,term",
    [
        ("결제 메모리 OOM 재시작", "OutOfMemoryError"),
        ("TLS 인증서 갱신 실패", "SSL handshake"),
        ("디스크 고갈", "No space left on device"),
    ],
)
def test_glossary_retrieves_terms_across_independent_sources(question, term):
    from fivewhys.desk.vocabulary import relevant_vocabulary

    selected = relevant_vocabulary(question)
    assert any(term in options for options in selected.values())
    assert all(
        "HikariPool connection pool" not in options for options in selected.values()
    )
    assert relevant_vocabulary("unseen zeppelin") == {}


def test_vocabulary_plan_rejects_terms_not_offered(monkeypatch):
    planner = LocalPlanner()
    raw = completion(
        '{"first_tool":"search_logs","log_query":"invented","report_query":"OOMKiller"}'
    )
    monkeypatch.setattr(planner, "_post", lambda payload: raw)
    with pytest.raises(LocalModelError, match="outside"):
        asyncio.run(planner("결제 OOM", SPECS))
