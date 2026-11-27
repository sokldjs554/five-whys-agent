"""Bounded loopback-only benchmark. Run with the Python environment of the desk."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import shutil
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
QUESTION = "주문 서비스의 DB 연결 풀 오류와 관련된 배포를 조사해 줘"
READ_STAGES = (1, 4, 12)
READS = 96
BURST = 42
CLIENTS = 12
DEADLINE = 300
http = build_opener(ProxyHandler({}))


def stats(numbers):
    values = sorted(numbers)
    if not values:
        return None

    def quantile(q):
        return round(values[math.ceil(len(values) * q) - 1], 2)

    return {
        "n": len(values),
        "p50_ms": quantile(0.5),
        "p95_ms": quantile(0.95),
        "max_ms": round(values[-1], 2),
    }


def source_digest(src):
    fingerprint = hashlib.sha256()
    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        fingerprint.update(path.relative_to(src).as_posix().encode() + b"\0")
        fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
    return fingerprint.hexdigest()


def rss_tree_kib(pid):
    if not Path("/proc/self/status").is_file():
        return None
    children = {}
    by_pid = {}
    for proc in Path("/proc").glob("[0-9]*"):
        try:
            fields = (proc / "stat").read_text().rsplit(")", 1)[1].split()
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        child = int(proc.name)
        children.setdefault(int(fields[1]), []).append(child)
        by_pid[child] = int(fields[21])
    pages = 0
    todo = [pid]
    while todo:
        current = todo.pop()
        pages += by_pid.get(current, 0)
        todo.extend(children.get(current, []))
    return pages * os.sysconf("SC_PAGE_SIZE") // 1024


def sampler(pid, db, t0, stop, samples):
    while not stop.is_set():
        counts = {}
        if db.exists():
            try:
                conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=0.05)
                try:
                    counts = dict(
                        conn.execute(
                            "SELECT status, count(*) FROM desk_jobs GROUP BY status"
                        )
                    )
                finally:
                    conn.close()
            except sqlite3.Error:
                pass
        samples.append(
            {
                "t_s": round(time.monotonic() - t0, 3),
                "queued": counts.get("queued", 0),
                "running": counts.get("running", 0),
                "server_tree_rss_kib": rss_tree_kib(pid),
            }
        )
        stop.wait(0.25)


class Run:
    def __init__(self, port, t0):
        self.base = f"http://127.0.0.1:{port}"
        self.t0 = t0
        self.rows = []
        self.jobs = []
        self.stages = []

    def call(self, phase, route, data=None):
        start = time.monotonic()
        if start - self.t0 > DEADLINE:
            raise TimeoutError("Benchmark deadline exceeded")
        body = json.dumps(data, ensure_ascii=False).encode() if data else None
        req = Request(
            self.base + route, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with http.open(req, timeout=5) as response:
                code, value, retry = response.status, json.load(response), None
        except HTTPError as error:
            code, value, retry = error.code, {}, error.headers.get("Retry-After")
        except (URLError, TimeoutError, ConnectionError) as error:
            code, value, retry = type(error).__name__, {}, None
        row = {
            "phase": phase,
            "t_s": round(start - self.t0, 5),
            "ms": round((time.monotonic() - start) * 1000, 3),
            "status": code,
        }
        if retry is not None:
            row["retry_after_s"] = retry
        self.rows.append(row)
        return code, value

    def submit(self, phase):
        status, result = self.call(
            phase, "/desk/jobs", {"engine": "rules", "question": QUESTION}
        )
        if status == 202:
            return result["id"]
        return None

    def finish(self, phase, job_id):
        path = "/desk/jobs/" + job_id
        while True:
            code, job = self.call(phase + "_poll", path)
            if code != 200:
                raise RuntimeError(f"Status GET returned {code}")
            if job["status"] not in {"queued", "running"}:
                break
            time.sleep(0.5)
        code, report = self.call(phase + "_verify", path + "/result")
        if (
            job["status"] != "completed"
            or code != 200
            or report.get("status") != "answered"
            or report["model_calls"] != 0
            or len(report["steps"]) != 3
            or not report["citations"]
        ):
            raise RuntimeError(
                f"Invalid terminal result for {job_id}: {job['status']}, {code}"
            )
        self.jobs.append(
            {
                "phase": phase,
                "id": job_id,
                "status": job["status"],
                "tool_calls": len(report["steps"]),
                "citations": len(report["citations"]),
                "queue_ms": round(1000 * (job["started_at"] - job["created_at"]), 3),
                "execution_ms": round(
                    1000 * (job["finished_at"] - job["started_at"]), 3
                ),
                "end_to_end_ms": round(
                    1000 * (job["finished_at"] - job["created_at"]), 3
                ),
            }
        )

    def run(self):
        seed = self.submit("warmup")
        self.finish("warmup", seed)
        for n in READ_STAGES:
            phase = f"read_c{n}"

            def read(_, phase=phase):
                code, report = self.call(phase, "/desk/jobs/" + seed + "/result")
                if code == 200 and (
                    report.get("id") != seed or report.get("status") != "answered"
                ):
                    raise ValueError("Result mismatch")

            start = time.monotonic()
            with concurrent.futures.ThreadPoolExecutor(n) as pool:
                list(pool.map(read, range(READS)))
            self.stages.append(
                {
                    "phase": phase,
                    "concurrency": n,
                    "count": READS,
                    "duration_s": round(time.monotonic() - start, 4),
                }
            )
        start = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(CLIENTS) as pool:
            ids = list(pool.map(lambda _: self.submit("burst_submit"), range(BURST)))
        submit_end = time.monotonic()
        for job_id in filter(None, ids):
            self.finish("burst", job_id)
        self.stages.append(
            {
                "phase": "burst_submit",
                "concurrency": CLIENTS,
                "count": BURST,
                "duration_s": round(submit_end - start, 4),
                "submit_and_drain_s": round(time.monotonic() - start, 4),
            }
        )
        followup = self.submit("recovery")
        if not followup:
            raise RuntimeError("Post-drain request rejected")
        self.finish("recovery", followup)

    def summary(self):
        output = {}
        for phase in sorted({r["phase"] for r in self.rows}):
            batch = [r for r in self.rows if r["phase"] == phase]
            output[phase] = {
                "http_statuses": dict(Counter(str(r["status"]) for r in batch)),
                "request_latency": stats(r["ms"] for r in batch),
            }
        burst = [j for j in self.jobs if j["phase"] == "burst"]
        return {
            "requests_by_phase": output,
            "burst_jobs": {
                key: stats(j[key] for j in burst)
                for key in ("queue_ms", "execution_ms", "end_to_end_ms")
            },
        }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, required=True, help="New JSON output path")
    args = cli.parse_args()
    if args.output.exists():
        cli.error("Choose a new output file")
    with tempfile.TemporaryDirectory(prefix="fivewhys-bench-") as tmp:
        sandbox = Path(tmp)
        src = sandbox / "src"
        shutil.copytree(
            ROOT / "src" / "fivewhys",
            src / "fivewhys",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        # Both 'python -m uvicorn' and the MCP subprocess resolve modules in this frozen cwd.
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(sandbox),
            "LANG": "C.UTF-8",
            "DESK_DB": str(sandbox / "jobs.db"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        snapshot = source_digest(src)
        with socket.socket() as listener, (sandbox / "server.log").open("w") as log:
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            t0 = time.monotonic()
            start = datetime.now(timezone.utc).isoformat()
            run = Run(listener.getsockname()[1], t0)
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "fivewhys.api:app",
                    "--fd",
                    str(listener.fileno()),
                    "--no-access-log",
                    "--workers",
                    "1",
                ],
                cwd=src,
                env=env,
                pass_fds=[listener.fileno()],
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
            samples, stop = [], threading.Event()
            monitor = threading.Thread(
                target=sampler, args=(proc.pid, sandbox / "jobs.db", t0, stop, samples)
            )
            try:
                monitor.start()
                while True:
                    if proc.poll() is not None or time.monotonic() - t0 > 30:
                        raise RuntimeError((sandbox / "server.log").read_text()[-2000:])
                    try:
                        with http.open(
                            run.base + "/desk/config", timeout=0.25
                        ) as status:
                            if status.status == 200:
                                break
                    except (URLError, TimeoutError):
                        time.sleep(0.1)
                run.run()
            finally:
                stop.set()
                monitor.join()
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
        cg = Path("/sys/fs/cgroup")
        result = {
            "utc_started": start,
            "source_sha256": snapshot,
            "python": platform.python_version(),
            "kernel": platform.release(),
            "versions": {
                v: importlib.metadata.version(v)
                for v in ("fastapi", "uvicorn", "mcp", "langgraph")
            },
            "cgroup": {
                f: (cg / f).read_text().strip()
                for f in ("cpu.max", "memory.max", "cpuset.cpus.effective")
                if (cg / f).is_file()
            },
            "settings": {
                "redis": False,
                "llm_calls": 0,
                "workers": 1,
                "engine": "rules",
                "client": "urllib HTTP/1.1, connection per request",
                "poll_seconds": 0.5,
                "queue_sampler_seconds": 0.25,
                "deadline_seconds": DEADLINE,
            },
            "stages": run.stages,
            "summary": run.summary(),
            "peak_sampled_active": max(s["queued"] + s["running"] for s in samples),
            "peak_sampled_server_tree_rss_kib": max(
                (s["server_tree_rss_kib"] or 0) for s in samples
            ),
            "jobs": run.jobs,
            "requests": sorted(run.rows, key=lambda r: r["t_s"]),
            "samples": samples,
        }
        if (
            result["summary"]["requests_by_phase"]["burst_submit"]["http_statuses"].get(
                "202", 0
            )
            == 0
        ):
            raise RuntimeError("No burst job was admitted")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x") as out:
            json.dump(result, out, ensure_ascii=False, separators=(",", ":"))
            out.write("\n")
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "stages",
                        "summary",
                        "peak_sampled_active",
                        "peak_sampled_server_tree_rss_kib",
                    )
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
