"""Bounded LangGraph investigation over a fresh MCP stdio session per request."""

from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from fivewhys.desk.evidence import in_scope, verify
from fivewhys.desk.mcp_tools import DeskError, desk_session, discover, read_rows, validate_plan

MESSAGES = {
    "out_of_scope": "현재 자료로 답할 수 있는 범위는 주문 서비스의 DB 커넥션 장애와 관련 배포 이력입니다.",
    "insufficient_evidence": "현재 로그, 배포 이력, 유사 장애 문서에서 일치하는 근거를 모두 찾지 못해 판단을 보류했습니다.",
    "conflict": "근거 기록이 서로 충돌하거나 배포 후보가 여러 개여서 원인 판단을 보류했습니다.",
    "invalid_plan": "조사 계획의 도구 또는 인자가 허용 범위를 벗어나 실행을 중단했습니다.",
    "invalid_result": "도구 응답을 검증할 수 없어 판단을 보류했습니다.",
    "tool_error": "근거를 읽는 도구가 실패해 판단을 보류했습니다.",
    "model_error": "모델에서 조사 계획을 받지 못해 판단을 보류했습니다.",
    "timeout": "조사 제한 시간을 초과해 판단을 보류했습니다.",
}


async def offline_plan(question: str, tools: list[dict]) -> list[dict]:
    """Deterministic query routing, also usable as a no-model evaluation baseline."""
    lower = question.lower()
    log_args = {"query": "HikariPool Connection is not available timed out", "service": "order-service"}
    if "504" in lower or "게이트웨이" in lower or "gateway" in lower:
        log_args = {"query": "Upstream timeout responding 504", "service": "api-gateway"}
    elif "customer_ref" in lower or "슬로우" in lower or "slow query" in lower:
        log_args = {"query": "slow query customer_ref", "service": "mysql"}
    return [
        {"tool": "search_past_incidents", "input": {"query": "HikariPool connection pool " + question[:150], "k": 4}},
        {"tool": "search_logs", "input": {**log_args, "limit": 5}},
        {"tool": "list_change_events", "input": {}},
    ]


class Investigation(TypedDict, total=False):
    plan: list[dict]
    steps: list[dict]
    reason: str
    answer: str
    citations: list[dict]


def graph_for(session, specs, question, planner, result_hook, trace):
    async def plan(_state):
        if planner is not None:
            trace["model_calls"] += 1
        try:
            raw = await (planner or offline_plan)(question, specs)
            calls = validate_plan(raw)
        except (asyncio.TimeoutError, TimeoutError):
            return {"reason": "timeout"}
        except DeskError as error:
            return {"reason": error.reason}
        except Exception:
            return {"reason": "model_error"}
        finally:
            usage = getattr(planner, "last_usage", None)
            if isinstance(usage, dict):
                trace["model_usage"] = usage
        trace["plan"] = calls
        return {"plan": calls}

    async def execute(state):
        call = state["plan"][len(state["steps"])]
        step = {**call, "status": "running", "output": []}
        # Keep a live trace, including the in-flight call if the outer deadline expires.
        trace["steps"].append(step)
        try:
            rows = await read_rows(session, call, result_hook)
        except (asyncio.TimeoutError, TimeoutError):
            reason = "timeout"
        except DeskError as error:
            reason = error.reason
        except Exception:
            reason = "tool_error"
        else:
            step.update(status="ok", output=rows)
            return {"steps": [*state["steps"], step]}
        step["status"] = reason
        return {"reason": reason, "steps": [*state["steps"], step]}

    def decide(state):
        try:
            answer, citations = verify(state["steps"], question)
            return {"reason": "verified", "answer": answer, "citations": citations}
        except DeskError as error:
            return {"reason": error.reason}

    def next_step(state):
        if state.get("reason"):
            return END
        return "verify" if len(state["steps"]) == len(state["plan"]) else "read"

    graph = StateGraph(Investigation)
    graph.add_node("plan_calls", plan)
    graph.add_node("read", execute)
    graph.add_node("verify", decide)
    graph.add_edge(START, "plan_calls")
    graph.add_conditional_edges("plan_calls", next_step)
    graph.add_conditional_edges("read", next_step)
    graph.add_edge("verify", END)
    return graph.compile()


async def investigate(question: str, *, planner=None, session_factory=None,
                      timeout_seconds: float = 30.0, _result_hook=None) -> dict:
    """Investigate the bundled incident. Fault injection is an internal Python-only seam.

    A supplied async planner receives the question and three discovered tool specs. The
    caller may supply a session factory for offline protocol tests; normal requests
    initialize, discover and call the shared server via the MCP SDK's stdio transport.
    """
    trace = {
        "question": question, "engine": "langgraph+mcp-stdio/" + ("model" if planner else "offline"),
        "model_calls": 0, "plan": [], "steps": [], "citations": [],
    }

    async def run():
        # Enter and leave MCP's AnyIO task groups in the same task.
        async with (session_factory or desk_session)() as session:
            specs = await discover(session)
            graph = graph_for(session, specs, question, planner, _result_hook, trace)
            return await graph.ainvoke({"steps": []}, config={"recursion_limit": 8})

    reason = "out_of_scope"
    if in_scope(question):
        try:
            state = await asyncio.wait_for(run(), timeout_seconds)
        except (asyncio.TimeoutError, TimeoutError):
            reason = "timeout"
        except DeskError as error:
            reason = error.reason
        except Exception:
            reason = "tool_error"
        else:
            reason = state["reason"]
            if reason == "verified":
                return {**trace, "status": "answered", "reason": reason,
                        "answer": state["answer"], "citations": state["citations"]}
    for step in trace["steps"]:
        if step["status"] == "running":
            step["status"] = reason
    return {**trace, "status": "withheld", "reason": reason, "answer": MESSAGES[reason]}
