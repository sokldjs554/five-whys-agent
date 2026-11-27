"""Compare two cited historical incidents on frozen questions. Run from the repository root."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import math
import statistics
import os
from pathlib import Path
import platform
import re
import sys
import time

from desk_eval import score as original_score, trace_supports

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs/desk/evaluation/comparison"
REPORTS = Path("src/fivewhys/data/postmortems")


def load(path):
    return json.loads(path.read_text())


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(text):
    return " ".join(text.casefold().split())


def original_label(case):
    if case["group"].startswith("original-"):
        split = case["group"].removeprefix("original-")
        return next(c for c in load(DATA.parent/(split+".json")) if c["id"] == case["id"])
    return None


def current_observations(steps, citations):
    ids = {c["id"] for c in citations}
    change = False
    symptom = False
    start = datetime.fromisoformat("2026-07-03T14:00:00+09:00")
    end = datetime.fromisoformat("2026-07-03T14:15:00+09:00")
    for step in steps:
        for row in step["output"]:
            if step["tool"] == "list_change_events" and f"change:{row['id']}" in ids:
                change |= (row["kind"] == "deploy" and row["service"] == "order-service"
                           and "v2.4.0" in row["description"] and "customer_ref" in row["description"]
                           and datetime.fromisoformat(row["ts"]) <= start)
            if step["tool"] == "search_logs" and f"log:{row['id']}" in ids:
                message = row["message"].lower()
                if row["level"] in {"WARN", "ERROR", "FATAL"} and start <= datetime.fromisoformat(row["ts"]) <= end:
                    symptom |= (
                        row["service"] == "order-service" and ("hikaripool" in message or "sqltransientconnectionexception" in message)
                        or row["service"] == "mysql" and "slow query" in message and "customer_ref" in message
                        or row["service"] == "api-gateway" and "504" in message and "order-service" in message
                    )
    return bool(change and symptom)


def assess(case, run, source_root, injected):
    steps, citations = run["steps"], run["citations"]
    answer = run["answer"]
    docs = set(case["documents"])
    rows = [r for step in steps if step["tool"] == "search_past_incidents"
            for r in step["output"] if isinstance(r, dict)]
    retrieved = {r["doc"] for r in rows}
    cited = set()
    grounded_docs = set()
    explained = set()
    bad_citations = []
    # Check the passage immediately preceding each reference. This rejects an
    # answer that attributes the cache mechanism to the pool report or vice versa.
    segments = {}
    previous_end = 0
    for match in re.finditer(r"\[((?:doc|log|change):[^\]]+)\]",answer):
        segments.setdefault(match[1], []).append(answer[previous_end:match.start()])
        previous_end = match.end()
    for citation in citations:
        cid = citation["id"]
        if cid not in segments or not trace_supports(citation,steps):
            bad_citations.append(cid)
            continue
        if not cid.startswith("doc:"):
            continue
        doc = cid.split(":")[1]
        cited.add(doc)
        if doc not in docs:
            continue
        row = next((r for r in rows if r["doc"] == doc and citation["text"] == r["text"]),None)
        if row is None:
            bad_citations.append(cid)
            continue
        body = row["text"].removeprefix(row["section"] + "\n").strip()
        original = (source_root/REPORTS/(doc+".md")).read_text()
        if not body or body not in original:
            bad_citations.append(cid)
            continue
        grounded_docs.add(doc)
        for segment in segments[cid]:
            # Require a literal source phrase in the visible answer as well as
            # conceptual coverage, beyond merely attaching the passage.
            plain = normalize(segment)
            source = normalize(body)
            literal = any(source[i:i+12] in plain for i in range(max(0, len(source)-11)))
            groups = case["mechanisms"][doc]
            if literal and all(any(normalize(t) in plain for t in group) for group in groups):
                explained.add(doc)
    families = {c["id"].split(":",1)[0] for c in citations}
    current_ok = (current_observations(steps,citations) and "v2.4.0" in answer) if case["current"] else (
        not families.intersection({"log","change"})
    )
    expected = case["expected"]
    old = original_label(case)
    original_result = original_score(old,run) if old else None
    if expected == "answered":
        passed = (run["status"] == "answered" and docs <= retrieved and docs == cited
                  and docs == grounded_docs == explained and current_ok and not bad_citations)
    elif case["fault"]:
        passed = (run["status"] == "withheld" and run["reason"] == "insufficient_evidence"
                  and injected and not citations)
    else:
        passed = run["status"] == "withheld" and run["reason"] in {
            "out_of_scope","insufficient_evidence","ambiguous_request","ambiguous_reports"
        } and not citations
    return {"pass": bool(passed and (original_result is None or original_result["passed"])),
            "retrieved_documents": sorted(retrieved), "cited_documents": sorted(cited),
            "verbatim_documents": sorted(grounded_docs), "explained_documents": sorted(explained),
            "invalid_citations":bad_citations, "current_evidence_ok":current_ok,
            "fault_triggered":injected, "original_gold_score":original_result}


async def run_mode(args):
    args.output_dir.mkdir(parents=True, exist_ok=True)
    src = args.source_root.resolve()
    sys.path.insert(0,str(src/"src"))
    os.environ["PYTHONPATH"] = os.pathsep.join([str(src/"src"),os.environ.get("PYTHONPATH","")])
    from fivewhys.desk.engine import investigate
    from fivewhys.desk.local_model import LocalPlanner

    frozen = load(DATA/"freeze.json")
    for path, expected in frozen["sha256"].items():
        source = src/path if path.startswith("src/") else ROOT/path
        if digest(source) != expected:
            raise SystemExit(f"Frozen input mismatch: {source}")
    records = []
    cases = load(DATA/"cases.json")
    if args.original_only:
        cases = [c for c in cases if c["group"].startswith("original-")]
    start = datetime.now(timezone.utc).isoformat()
    engine_hashes = {p.name:digest(p) for p in sorted((src/"src/fivewhys/desk").glob("*.py"))}
    for iteration in range(1,args.repeats+1):
        for case in cases:
            injected = False
            def hook(name, rows):
                nonlocal injected
                if case["fault"] == "empty_current_logs" and name == "search_logs":
                    injected = True
                    return []
                if case["fault"] == "missing_second_report" and name == "search_past_incidents":
                    missing = case["documents"][1]
                    filtered = [r for r in rows if r["doc"] != missing]
                    if len(rows) != len(filtered):
                        injected = True
                    return filtered
                return rows

            planner = LocalPlanner.from_env() if args.mode == "local" else None
            t = time.perf_counter()
            result = await investigate(case["question"],planner=planner,timeout_seconds=args.timeout,
                                       _result_hook=hook if case["fault"] else None)
            wall_ms = round((time.perf_counter()-t)*1000,1)
            scored = assess(case,result,src,injected)
            r = {"id":case["id"],"mode":args.mode,"iteration":iteration,"fault":case["fault"],
                 "elapsed_ms":wall_ms,"run":result,"score":scored}
            records.append(r)
            print(iteration,case["id"],result["reason"],scored["pass"],flush=True)
    prefix = args.output_dir/args.mode
    with prefix.with_suffix(".jsonl").open("w") as f:
        for row in records:
            f.write(json.dumps(row,ensure_ascii=False)+"\n")
    batches = {}
    for case in cases:
        rr = [r for r in records if r["id"] == case["id"]]
        batches[case["id"]] = {"pass":sum(r["score"]["pass"] for r in rr),"total":len(rr),
                               "reasons":dict(Counter(r["run"]["reason"] for r in rr))}
    passing = sum(r["score"]["pass"] for r in records)
    usages = [r["run"].get("model_usage") or {} for r in records]
    model_ids = {u["request_id"] for u in usages if u.get("request_id")}
    latency = sorted(r["elapsed_ms"] for r in records)
    subsets = {}
    for status in ("answered","withheld"):
        ids = {c["id"] for c in cases if c["expected"] == status}
        group = [r for r in records if r["id"] in ids]
        subsets[status] = {"pass":sum(r["score"]["pass"] for r in group),"runs":len(group)}
    summary = {"started_utc":start,"environment":{"python":platform.python_version(),"platform":platform.platform(),
        "dependencies":{p:metadata.version(p) for p in ["mcp","langgraph","pydantic","numpy"]},
        "planner_version":os.environ.get("FIVEWHYS_PLANNER_VERSION","v2") if planner else None,
        "implementation_sha256":engine_hashes,"cases_sha256":digest(DATA/"cases.json")},
        "repetitions":args.repeats,"cases":len(cases),"passed":passing,"total":len(records),
        "distinct_model_response_ids":len(model_ids),"prompt_tokens":sum(u.get("prompt_tokens",0) for u in usages),
        "completion_tokens":sum(u.get("completion_tokens",0) for u in usages),
        "attempted_tool_calls":sum(len(r["run"]["steps"]) for r in records),"by_case":batches,
        "by_expected":subsets, "latency_ms":{"p50":round(statistics.median(latency),1),
                                              "p95":latency[math.ceil(.95*len(latency))-1]}}
    dump(prefix.with_suffix(".summary.json"),summary)


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=["offline","local"],default="offline")
    p.add_argument("--repeats",type=int,default=3)
    p.add_argument("--timeout",type=float,default=60)
    p.add_argument("--source-root",type=Path,default=ROOT)
    p.add_argument("--output-dir",type=Path,default=DATA/"after")
    p.add_argument("--original-only",action="store_true")
    args=p.parse_args()
    if args.repeats < 1:
        p.error("--repeats must be positive")
    asyncio.run(run_mode(args))
