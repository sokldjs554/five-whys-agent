"""Repeat the frozen incident-desk cases and export auditable traces, scores and replays."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import statistics
import sys
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/desk/evaluation"
sys.path.insert(0, str(ROOT / "src"))


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def validate_freeze():
    hashes = {**read(DATA / "freeze.json")["sha256"], **read(DATA/"challenge-freeze.json")["sha256"]}
    for path, expected in hashes.items():
        if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
            raise SystemExit(f"Frozen input changed: {path}")


def fixture_kwargs(name):
    from fivewhys.desk.mcp_tools import desk_session
    from mcp.types import CallToolResult, TextContent

    if name in ("provider_error", "invalid_arguments", "invalid_arguments_type"):
        async def faulty_planner(question, tools):
            if name == "provider_error":
                raise HTTPError("http://fixture.invalid/model", 503, "fixture: unavailable", {}, None)
            args = {"query": "HikariPool", "limit": -1 if name == "invalid_arguments" else "5"}
            return [{"tool": "list_change_events", "input": {}},
                    {"tool": "search_logs", "input": args},
                    {"tool": "search_past_incidents", "input": {"query": "커넥션 풀"}}]
        return {"planner": faulty_planner}

    if name in ("tool_error", "tool_timeout"):
        class FaultyClient:
            def __init__(self, client):
                self.initialize = client.initialize
                self.list_tools = client.list_tools
                self.client = client

            async def call_tool(self, tool, args):
                if tool == "search_logs":
                    if name == "tool_timeout":
                        raise TimeoutError("fixture: log tool deadline exceeded")
                    return CallToolResult(isError=True, content=[TextContent(
                        type="text", text="fixture: log index unavailable")])
                return await self.client.call_tool(tool, args)

        @asynccontextmanager
        async def failing_session():
            async with desk_session() as client:
                yield FaultyClient(client)
        return {"session_factory": failing_session}

    def change_result(tool, rows):
        if (name == "empty_logs" and tool == "search_logs") or (
            name == "empty_docs" and tool == "search_past_incidents"
        ):
            return []
        if tool == "list_change_events" and name == "conflicting_deployments":
            record = next(row for row in rows if row["service"] == "order-service")
            competing = {**record, "id": max(row["id"] for row in rows) + 1,
                         "description": record["description"].replace("v2.4.0", "v2.8.9")}
            return [*rows, competing]
        return rows
    return {"_result_hook": change_result} if name else {}


def normalized(value):
    return " ".join(value.casefold().split())


def score(case, run):
    steps = run["steps"]
    docs = [
        row["doc"] for step in steps if step["tool"] == "search_past_incidents"
        for row in step.get("output") or [] if isinstance(row, dict) and "doc" in row
    ]
    gold = set(case["relevant_docs"])
    ranked = list(dict.fromkeys(docs))
    matched = gold.intersection(ranked)
    plan = [action["tool"] for action in run.get("plan", [])]
    expected = case["required_tools"]
    selected = sorted(plan) == sorted(expected) if expected is not None else None
    missing_terms = [group for group in case["required_terms"] if not any(
        normalized(term) in normalized(run["answer"]) for term in group)]
    citations = run["citations"]
    families = {c["id"].split(":", 1)[0] for c in citations}
    missing_families = sorted(set(case["citation_families"]) - families)
    missing_doc_citations = sorted(doc for doc in gold if not any(
        doc in str(c["id"]) or doc in str(c.get("source", "")) for c in citations))
    # A cited excerpt must be present in the returned observation for that exact source.
    unsupported = [c["id"] for c in citations if not trace_supports(c, steps)]
    positive = case["expected_status"] == "answered"
    grounded = (run["status"] == "answered" and not (
        missing_terms or missing_families or missing_doc_citations or unsupported)
    ) if positive else None
    abstained = (run["status"] == "withheld" and not citations and
                 run["reason"] == case["expected_reason"]) if not positive else None
    return {
        "retrieved_documents": ranked, "relevant_documents_found": len(matched),
        "relevant_documents_expected": len(gold),
        "retrieval_recall": len(matched)/len(gold) if gold else None,
        "tool_selection_exact": selected, "attempted_tools": len(steps),
        "successful_tools": sum(isinstance(step.get("output"), list) and
                                step.get("status") == "ok" for step in steps),
        "missing_claim_groups": missing_terms, "missing_source_types": missing_families,
        "missing_document_citations": missing_doc_citations,
        "unsupported_citations": unsupported, "grounded_answer": grounded,
        "correct_abstention": abstained, "passed": grounded if positive else abstained,
    }


def trace_supports(citation, steps):
    cid = citation["id"]
    excerpt = normalized(citation["text"])
    if not excerpt:
        return False
    for step in steps:
        for row in step.get("output") or []:
            if not isinstance(row, dict):
                continue
            if step["tool"] == "search_logs":
                match = cid == f"log:{row['id']}"
                source = row["message"]
            elif step["tool"] == "list_change_events":
                match = cid == f"change:{row['id']}"
                source = row["description"]
            elif step["tool"] == "search_past_incidents":
                digest = hashlib.sha256(row["text"].encode()).hexdigest()[:10]
                match = cid == f"doc:{row['doc']}:{digest}"
                source = row["text"]
            else:
                continue
            if match and excerpt in normalized(source):
                return True
    return False


def summarize(records):
    scores = [r["score"] for r in records]
    def bool_rate(field):
        values = [s[field] for s in scores if s[field] is not None]
        return {"success": sum(values), "total": len(values)}
    times = sorted(r["latency_ms"] for r in records)
    return {
        "cases": len({r["id"] for r in records}), "runs": len(records),
        "retrieval_recall_micro": {"found": sum(s["relevant_documents_found"] for s in scores),
                                   "expected": sum(s["relevant_documents_expected"] for s in scores)},
        "tool_selection": bool_rate("tool_selection_exact"),
        "tool_execution": {"success": sum(s["successful_tools"] for s in scores),
                           "attempted": sum(s["attempted_tools"] for s in scores)},
        "grounded_answer": bool_rate("grounded_answer"), "correct_abstention": bool_rate("correct_abstention"),
        "end_to_end": bool_rate("passed"),
        "failed_runs": dict(Counter(r["id"] for r in records if not r["score"]["passed"])),
        "mixed_outcome_cases": [id for id in sorted({r["id"] for r in records})
                                if len({r["score"]["passed"] for r in records if r["id"] == id}) > 1],
        "latency_ms_p50": round(statistics.median(times), 1),
        "latency_ms_p95": times[math.ceil(len(times)*.95)-1],
        "actual_local_model_requests": sum(r["model_requests"] for r in records),
        "prompt_tokens": sum(r["model_usage"].get("prompt_tokens",0) for r in records),
        "completion_tokens": sum(r["model_usage"].get("completion_tokens",0) for r in records),
        "planner_calls_reported_by_engine": sum(r["run"]["model_calls"] for r in records),
    }


async def evaluate(args):
    args.results_dir.mkdir(parents=True, exist_ok=True)
    from fivewhys.desk.engine import investigate
    validate_freeze()
    tag = f"{args.mode}-{args.split}"
    cases = read(DATA / f"{args.split}.json")
    env = {
        "python": sys.version, "system": platform.system(), "machine": platform.machine(),
        "dependencies": {p: importlib.metadata.version(p) for p in ("mcp","langgraph","numpy","pydantic")},
        "frozen_inputs_sha256": hashlib.sha256((DATA/"freeze.json").read_bytes()).hexdigest(),
        "mode": args.mode, "split": args.split, "repetitions": args.repeats,
        "planner_version": os.environ.get("FIVEWHYS_PLANNER_VERSION","v2") if args.mode == "local" else None,
        "embedding_mode": "served" if os.environ.get("DESK_EMBEDDING_URL") else "hashing",
        "split_definition_sha256": hashlib.sha256((DATA/f"{args.split}.json").read_bytes()).hexdigest(),
        "implementation_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted((ROOT/"src/fivewhys/desk").glob("*.py"))
                                  if p.name in {"engine.py","evidence.py","mcp_tools.py","local_model.py","vocabulary.py"}},
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    records = []
    with (args.results_dir/f"{tag}.jsonl").open("w") as raw:
        for cycle in range(1, args.repeats+1):
            for case in cases:
                kwargs = fixture_kwargs(case["fixture"])
                actual_model = args.mode == "local" and "planner" not in kwargs
                model_requests = 0
                usage = {}
                if actual_model:
                    from fivewhys.desk.local_model import LocalPlanner
                    planner = LocalPlanner.from_env()
                    async def measured(question, tools):
                        nonlocal model_requests, usage
                        model_requests += 1
                        try:
                            return await planner(question, tools)
                        finally:
                            usage = dict(getattr(planner, "last_usage", {}) or {})
                    kwargs["planner"] = measured
                start = time.perf_counter()
                run = await investigate(case["question"], timeout_seconds=args.timeout, **kwargs)
                record = {"id": case["id"], "split": args.split, "cycle": cycle,
                          "fixture": case["fixture"], "expected_status": case["expected_status"],
                          "expected_reason": case["expected_reason"], "model_requests": model_requests,
                          "model_usage": usage, "latency_ms": round((time.perf_counter()-start)*1000,1),
                          "run": run, "score": score(case,run)}
                records.append(record)
                raw.write(json.dumps(record, ensure_ascii=False) + "\n")
                raw.flush()
                print(tag, cycle, case["id"], run["reason"], record["score"]["passed"], flush=True)
    write(args.results_dir/f"{tag}-summary.json", {"environment":env,"summary":summarize(records)})


def export_replays(results_dir):
    runs = []
    for id, title in [
        ("dev-01","주문 장애 원인 조사"), ("dev-02","영어로 조회한 배포 이력"),
        ("hold-03","두 과거 보고서 비교"),
        ("hold-04","고객 정보 요청"), ("hold-05","서로 다른 배포 기록"),
        ("hold-06","로그 도구 오류"), ("hold-10","로그 도구 타임아웃"),
    ]:
        split = "development" if id.startswith("dev") else "heldout"
        # Prefer a real local model trace when present, including failed runs.
        for mode in ("local","offline"):
            source = results_dir / f"{mode}-{split}.jsonl"
            if not source.exists():
                continue
            record = next((r for r in map(json.loads,source.read_text().splitlines()) if r["id"] == id),None)
            if record:
                runs.append({**record["run"],"id": id,"title":title,
                             "evaluation_mode":mode, "evaluation_passed":record["score"]["passed"],
                             "elapsed_ms":record["latency_ms"],"fixture":record["fixture"],
                             "model_usage":record["model_usage"], "model_requests":record["model_requests"]})
                break
    if not runs:
        raise SystemExit("Run evaluation before exporting replays")
    write(ROOT/"desk-demo/runs.json",runs)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=["offline","local"],default="offline")
    p.add_argument("--split",choices=["development","heldout","challenge"],default="development")
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--timeout",type=float,default=45.0)
    p.add_argument("--results-dir", type=Path, default=DATA)
    p.add_argument("--export-replays",action="store_true")
    args=p.parse_args()
    if args.export_replays:
        export_replays(args.results_dir)
    else:
        if args.repeats <= 0:
            p.error("--repeats must be positive")
        asyncio.run(evaluate(args))
