import asyncio
import sqlite3
import time

from fastapi.testclient import TestClient

from fivewhys.api import create_app
from fivewhys.desk.jobs import JobStore


async def fake_run(question, *, planner=None):
    return dict(question=question, status="answered", answer="합성 로그 1건", reason="",
                citations=[{"id":"log:1","source":"logs","text":"pool timeout"}],
                steps=[], model_calls=0, engine="rules")


def test_job_survives_restart(tmp_path):
    path = tmp_path / "jobs.db"
    with TestClient(create_app(desk_db=path, desk_runner=fake_run)) as client:
        accepted = client.post("/desk/jobs", json={"question":"주문 서비스 로그 조사"})
        assert accepted.status_code == 202
        job = accepted.json()["id"]
        for _ in range(100):
            state = client.get(f"/desk/jobs/{job}").json()
            if state["status"] == "completed":
                break
            time.sleep(.03)
        assert state["status"] == "completed"
        result = client.get(f"/desk/jobs/{job}/result").json()
        assert result["citations"][0]["id"] == "log:1"
    with TestClient(create_app(desk_db=path, desk_runner=fake_run)) as client:
        assert client.get(f"/desk/jobs/{job}/result").json() == result
        assert client.get("/desk/jobs/missing").status_code == 404
        assert client.post("/desk/jobs", json={"question":"     "}).status_code == 422


def test_only_one_worker_claims_and_expired_jobs_fail_closed(tmp_path):
    store = JobStore(tmp_path / "jobs.db")
    store.initialize()
    job = store.enqueue("주문 서비스 로그 조사", "rules")
    assert store.claim()["id"] == job
    assert store.claim() is None
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE desk_jobs SET expires_at=0")
    assert store.claim() is None
    assert store.read(job)["status"] == "failed"


def test_unavailable_and_failed_results(tmp_path):
    async def broken(*args, **kwargs):
        await asyncio.sleep(.2)
        raise ValueError("untrusted provider error")
    with TestClient(create_app(desk_db=tmp_path / "jobs.db", desk_runner=broken)) as client:
        job = client.post("/desk/jobs", json={"question":"주문 서비스 로그 조사"}).json()["id"]
        assert client.get(f"/desk/jobs/{job}/result").status_code == 409
        for _ in range(100):
            state = client.get(f"/desk/jobs/{job}").json()
            if state["status"] == "failed":
                break
            time.sleep(.03)
        assert state["status"] == "failed"
        assert state["error"] == "ValueError"
        assert client.get(f"/desk/jobs/{job}/result").json()["status"] == "withheld"


def test_followup_only_quotes_this_jobs_verified_evidence(tmp_path):
    path = tmp_path / "thread.db"
    with TestClient(create_app(desk_db=path, desk_runner=fake_run)) as client:
        job = client.post("/desk/jobs", json={"question":"주문 서비스 장애 조사"}).json()["id"]
        for _ in range(100):
            if client.get(f"/desk/jobs/{job}").json()["status"] == "completed":
                break
            time.sleep(.03)
        url = f"/desk/jobs/{job}/messages"
        assert client.post(url, json={"citation_id":"log:99"}).status_code == 404
        followup = client.post(url, json={"citation_id":"log:1"})
        assert followup.status_code == 201
        assert followup.json()["reply"]["text"] == "pool timeout"
    with TestClient(create_app(desk_db=path, desk_runner=fake_run)) as client:
        assert client.get(url).json() == [followup.json()]
