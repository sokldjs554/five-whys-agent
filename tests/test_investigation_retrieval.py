from datetime import timedelta
import hashlib
from pathlib import Path
import re

import pytest

from fivewhys.investigation.retrieval import _scope
from fivewhys.investigation.retrieval_corpus import REPORT_DIR, seed_rows, upload_rows
from fivewhys.scenarios.catalog import get_scenario


def test_seed_citations_resolve_to_original_sources():
    bundle = get_scenario("db_pool_exhaustion", 42)
    start, end = bundle.incident
    rows = seed_rows()
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        if row["kind"] == "report":
            source = (REPORT_DIR.parent / row["source"]).read_text(encoding="utf-8")
        elif row["kind"] == "log":
            service = row["service"]
            component, level = Path(row["source"]).stem.rsplit("-", 1)
            records = [x for x in bundle.logs if x.service == service and x.component == component
                       and x.level == level and start <= x.ts < end]
            source = "\n".join(f"{x.ts.isoformat()} {x.level} [{x.component}] {x.message}" for x in records)
            assert row["observed_at"] == records[0].ts.isoformat()
            assert row["end_at"] == records[-1].ts.isoformat()
        elif row["kind"] == "deployment":
            [event] = [x for x in bundle.deploys if start - timedelta(hours=1) <= x.ts <= start]
            assert bundle.ground_truth.culprit_change_match in event.description
            source = f"{event.ts.isoformat()} {event.kind} {event.description}"
        else:
            continue
        assert row["version"] == "sha256:" + hashlib.sha256(source.encode()).hexdigest()
        begin, last = map(int, re.fullmatch(r"L(\d+)-L(\d+)", row["locator"]).groups())
        assert row["text"] == "\n".join(source.splitlines()[begin - 1:last])
    assert all("orders" not in r["teams"] for r in rows if r["service"] == "mysql")
    # Compare the companion case to a separate original scenario, not the main incident.
    comparison = get_scenario("cache_stampede", 42)
    assert comparison.ground_truth.root_cause_service == "redis-cache"
    assert any(x.service == "order-service" and "Cache miss" in x.message for x in comparison.logs)
    assert any(x.service == "api-gateway" and "Upstream timeout" in x.message for x in comparison.logs)


def test_index_acl_version_and_semantic_boundaries():
    doc = dict(kind="runbook", source="manual.md", title="Recovery", service="api-gateway",
               text="# Recovery\n1. Inspect\n  collect records\n2. Restore", version="r1")
    initial = upload_rows([doc], "orders")
    assert initial == upload_rows([doc], "orders")
    assert [r["locator"] for r in initial] == ["L2-L3", "L4-L4"]
    revised = upload_rows([{**doc, "text": doc["text"] + " and verify"}], "orders")
    assert {r["id"] for r in initial}.isdisjoint(r["id"] for r in revised)
    other_team = upload_rows([doc], "platform")
    assert {r["id"] for r in initial}.isdisjoint(r["id"] for r in other_team)
    with pytest.raises(ValueError):
        upload_rows([{**doc, "teams": ["platform"]}], "orders")
    with pytest.raises(ValueError):
        _scope('orders" or true')
    with pytest.raises(ValueError):
        _scope("orders", "log or true")


def test_deployment_entries_own_their_multiline_notes():
    docs = [dict(kind="deployment", title="Releases", service="order-service", source="changes.txt",
                 text="2026-07-03 12:00 release A\n  note for A\n2026-07-03 13:20 release B\n  note for B")]
    rows = upload_rows(docs, "orders")
    assert [r["locator"] for r in rows] == ["L1-L2", "L3-L4"]
    assert rows[1]["text"].endswith("note for B")


def test_long_step_keeps_exact_body_and_rejects_unstorable_batch_before_connecting(monkeypatch):
    import json
    from fivewhys.investigation import retrieval
    text = "1. " + "조" * 10920
    doc = dict(kind="runbook", title="점검", source="manual.md", text=text, service="orders")
    [row] = upload_rows([doc], "orders")
    assert row["text"] == text and row["locator"] == "L1-L1"
    assert len(json.dumps(row, ensure_ascii=False).encode()) < 65536
    monkeypatch.setattr(retrieval, "_stores", lambda: pytest.fail("invalid batch must never write"))
    for invalid in ("bad\x00value", "\x01" * 32760):
        with pytest.raises(ValueError):
            retrieval.index_documents([doc, {**doc, "text": invalid}], "orders")


def test_judgments_require_distinct_immutable_ids_even_when_coordinates_collide():
    from fivewhys.evaluation.retrieval_benchmark import metrics
    same_coordinates = {"source": "archive.md", "locator": "L1-L3"}
    rows = [{"id": "foreign-version", **same_coordinates}, {"id": "gold", **same_coordinates},
            {"id": "gold", **same_coordinates}]
    assert metrics(rows, {"gold", "other-gold"}) == {"recall": 0.5, "reciprocal_rank": 0.5}
