import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
import json

import pytest

from fivewhys.desk.engine import investigate, offline_plan
from fivewhys.desk.mcp_tools import INPUTS

QUESTION = "주문 서비스의 커넥션 풀 장애는 어느 배포와 관련이 있어?"
LOG = {"id": 31, "ts": "2026-07-03T14:05:00+09:00", "service": "order-service",
       "level": "ERROR", "component": "db-pool",
       "message": "HikariPool-1 Connection is not available, request timed out"}
CHANGE = {"id": 2, "ts": "2026-07-03T13:20:00+09:00", "service": "order-service",
          "kind": "deploy", "description": "주문 조회 customer_ref 조건 추가 v2.4.0"}
DOC = {"doc": "2025-11-14-db-connection-pool", "section": "요약",
       "text": "요약\nHikariPool connection pool이 고갈되었다.", "score": 0.02}
ROWS = {"search_logs": [LOG], "list_change_events": [CHANGE], "search_past_incidents": [DOC]}


class StubSession:
    async def initialize(self):
        pass

    async def list_tools(self):
        return SimpleNamespace(tools=[
            SimpleNamespace(name=name, description=name) for name in INPUTS
        ])

    async def call_tool(self, name, args):
        body = SimpleNamespace(type="text", text=json.dumps(ROWS[name]))
        return SimpleNamespace(isError=False, content=[body])


@asynccontextmanager
async def stub():
    yield StubSession()


def run(**kwargs):
    return asyncio.run(investigate(QUESTION, session_factory=stub, **kwargs))


def test_real_stdio_run_has_verbatim_citations():
    result = asyncio.run(investigate(QUESTION))
    assert result["reason"] == "verified"
    assert result["model_calls"] == 0
    assert {s["tool"] for s in result["steps"]} == set(INPUTS)
    assert all(s["status"] == "ok" for s in result["steps"])
    fields = {value for step in result["steps"] for row in step["output"]
              for value in row.values() if isinstance(value, str)}
    for citation in result["citations"]:
        assert citation["text"] in fields
        assert "[" + citation["id"] + "]" in result["answer"]


def test_invalid_plan_is_rejected_before_dispatch():
    async def planner(question, specs):
        calls = await offline_plan(question, specs)
        calls[-1]["input"]["unknown"] = True
        return calls

    result = run(planner=planner)
    assert result["reason"] == "invalid_plan"
    assert result["steps"] == result["citations"] == []
    assert result["model_calls"] == 1


@pytest.mark.parametrize(("change_rows", "reason"), [
    ([], "insufficient_evidence"),
    ([CHANGE, {**CHANGE, "id": 3, "description": "order-service v2.5.0 deploy"}], "conflict"),
    ([{**CHANGE, "ts": "not a date"}], "invalid_result"),
    ([{**CHANGE, "id": "2"}], "invalid_result"),
])
def test_failures_withhold(change_rows, reason):
    result = run(_result_hook=lambda name, rows: change_rows if name == "list_change_events" else rows)
    assert result["status"] == "withheld"
    assert result["reason"] == reason
    assert result["citations"] == []


def test_whole_investigation_timeout_cancels_pending_operation():
    @asynccontextmanager
    async def stalled():
        await asyncio.sleep(2)
        yield StubSession()

    result = asyncio.run(investigate(QUESTION, session_factory=stalled, timeout_seconds=0.02))
    assert result["reason"] == "timeout"
    assert result["steps"] == []


def test_out_of_scope_skips_model_and_transport():
    def no_transport():
        pytest.fail("MCP was opened for an unsupported question")

    result = asyncio.run(investigate("이번 주문 장애로 인한 매출 손실은 얼마인가요?", session_factory=no_transport))
    assert result["reason"] == "out_of_scope"
    assert result["model_calls"] == 0


@pytest.mark.parametrize("question", [
    "주문 서비스 장애로 언제 복구됐나요?",
    "주문 서비스 DNS 배포의 인증서 발급자를 조사해 줘",
    "주문 장애는 유럽 리전인가요?",
    "Which Kubernetes worker caused the order-service incident?",
    "주문 장애의 원인을 과거 보고서 두 개로 각각 설명해 주세요.",
    "Is order-service v8.9.1 the cause of the incident?",
    "주문 서비스 장애의 원인은 東京 인가요?",
])
def test_uncovered_subject_or_attribute_is_withheld(question):
    assert asyncio.run(investigate(question, session_factory=stub))["reason"] == "out_of_scope"


def test_supported_generic_diagnosis_is_answered():
    result = asyncio.run(investigate("이번 주문 장애의 원인을 조사해 줘", session_factory=stub))
    assert result["reason"] == "verified"


@pytest.mark.parametrize("question", [
    "지금 주문이 자꾸 실패하는데 무슨 일이 벌어졌는지 로그를 짚어볼래요?",
    "Any clues in the logs as to why the order API started acting up?",
])
def test_diagnostic_paraphrases_reach_evidence_tools(question):
    result = asyncio.run(investigate(question, session_factory=stub))
    assert result["status"] == "answered"
    assert len(result["steps"]) == 3


def test_historical_document_is_selected_by_supported_passage():
    irrelevant = {**DOC, "text": "요약\nHikariPool 메트릭 이름을 변경했습니다. DNS 요청이 지연됐습니다."}
    renamed = {**DOC, "doc": "archived-incident-314"}
    result = run(_result_hook=lambda name, rows:
                 [irrelevant, renamed] if name == "search_past_incidents" else rows)
    assert result["reason"] == "verified"
    assert result["citations"][-1]["source"].startswith("postmortems/archived-incident-314.md")


@pytest.mark.parametrize("passage", [
    "HikariPool 메트릭을 추가했다. 장애 원인은 DNS 응답 지연이었다.",
    "HikariPool 고갈은 없었다. DNS 타임아웃이 발생했다.",
    "customer_ref 컬럼을 소개하는 문서다.",
    "HikariPool remained healthy while an unrelated DNS request timed out.",
])
def test_shared_keyword_cannot_confirm_historical_match(passage):
    result = run(_result_hook=lambda name, rows:
                 [{**DOC, "text": "요약\n" + passage}] if name == "search_past_incidents" else rows)
    assert result["reason"] == "insufficient_evidence"
