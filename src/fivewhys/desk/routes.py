"""Incident desk HTTP lifecycle. Requests are durable before returning 202."""
from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, StringConstraints

from .jobs import MAX_RUNTIME, JobStore


class Inquiry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=700)]
    engine: Literal["rules", "local"] = "rules"


class Followup(BaseModel):
    citation_id: Annotated[str, StringConstraints(min_length=1, max_length=250)]


async def run_investigation(question, *, planner=None):
    from .engine import investigate
    return await investigate(question, planner=planner)


class Desk:
    def __init__(self, path=None, runner=None):
        self.store = JobStore(path or os.getenv("DESK_DB", ".fivewhys/jobs.db"))
        self.runner = runner or run_investigation
        self.cache = None
        self.router = APIRouter(prefix="/desk")
        self.router.add_api_route("/config", self.config, methods=["GET"])
        self.router.add_api_route("/jobs", self.submit, methods=["POST"], status_code=202)
        self.router.add_api_route("/jobs/{job_id}", self.job, methods=["GET"])
        self.router.add_api_route("/jobs/{job_id}/result", self.result, methods=["GET"])

        self.router.add_api_route("/jobs/{job_id}/messages", self.messages, methods=["GET"])
        self.router.add_api_route("/jobs/{job_id}/messages", self.followup, methods=["POST"], status_code=201)

    def messages(self, job_id: str):
        self.job(job_id)
        return self.store.messages(job_id)

    def followup(self, job_id: str, req: Followup):
        record = self.result(job_id)
        for citation in record["citations"]:
            if citation["id"] == req.citation_id:
                return self.store.quote(job_id, citation)
        raise HTTPException(404, "이 작업에서 검증한 인용을 찾을 수 없습니다.")

    @asynccontextmanager
    async def lifespan(self, app):
        from .cache import make_cache_from_env
        self.cache = make_cache_from_env()
        self.store.initialize()
        self.wake = asyncio.Event()
        worker = asyncio.create_task(self.work())
        try:
            yield
        finally:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker

    async def work(self):
        while True:
            self.wake.clear()
            job = self.store.claim()
            if job is None:
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=1)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                planner = None
                if job["engine"] == "local":
                    from .local_model import LocalPlanner
                    planner = LocalPlanner.from_env()
                record = await asyncio.wait_for(
                    self.runner(job["question"], planner=planner), timeout=MAX_RUNTIME
                )
                if record.get("status") not in {"answered", "withheld"}:
                    raise ValueError("Invalid investigation status")
                self.store.finish(job["id"], result=record)
            except asyncio.CancelledError:
                self.store.finish(job["id"], error="WorkerStopped")
                raise
            except Exception as exc:
                self.store.finish(job["id"], error=type(exc).__name__)

    def config(self):
        return {"mode":"live", "engines":["rules","local"], "max_question_length":700}

    async def submit(self, req: Inquiry):
        try:
            job_id = self.store.enqueue(req.question, req.engine)
        except OverflowError:
            raise HTTPException(429, "대기열이 가득 찼습니다.", headers={"Retry-After":"5"})
        self.wake.set()
        return {"id": job_id, "status": "queued", "status_url": f"/desk/jobs/{job_id}",
                "result_url": f"/desk/jobs/{job_id}/result"}

    def job(self, job_id: str):
        job = self.store.read(job_id)
        if not job:
            raise HTTPException(404, "조사 기록을 찾을 수 없습니다.")
        return job

    def result(self, job_id: str):
        job = self.job(job_id)
        if job["status"] in {"queued", "running"}:
            raise HTTPException(409, "조사를 진행하고 있습니다.", headers={"Retry-After":"1"})
        if job["status"] == "failed":
            return {"id": job_id, "question":job["question"], "engine":job["engine"],
                    "status":"withheld", "answer":"", "reason":f"실행 중단 ({job['error']})",
                    "model_calls":None, "steps":[], "citations":[]}
        cached = self.cache.get(job_id)
        if cached is not None:
            return cached
        record = self.store.result(job_id)
        record["id"] = job_id
        self.cache.put(job_id, record)
        return record


def attach(app, desk):
    from fastapi.staticfiles import StaticFiles
    app.include_router(desk.router)
    assets = Path(os.getenv("DESK_ASSETS", Path(__file__).resolve().parents[3] / "desk-demo"))
    if assets.is_dir():
        app.mount("/desk", StaticFiles(directory=assets, html=True), name="desk-ui")
