"""Submit a real rules-mode incident and verify that its completed report is stable."""

import argparse
import hashlib
import json
import time
from urllib.request import Request, urlopen


def request(base, path, body=None):
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode()
    req = Request(base.rstrip("/") + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=10) as response:
        return response.status, json.load(response)


def smoke(base, existing=None):
    question = "주문 서비스의 DB 연결 풀 오류와 관련된 배포를 조사해 줘"
    history = []
    job_id = existing
    if existing is None:
        code, job = request(base, "/desk/jobs", {"question": question})
        assert code == 202 and job["status"] == "queued", job
        job_id = job["id"]
        history.append("queued")
    path = "/desk/jobs/" + job_id
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        _, status = request(base, path)
        state = status["status"]
        if not history or state != history[-1]:
            history.append(state)
        if state not in {"queued", "running"}:
            break
        time.sleep(0.5)
    assert history[-1] == "completed", history
    _, report = request(base, path + "/result")
    _, again = request(base, path + "/result")
    assert report == again
    assert report["id"] == job_id and report["status"] == "answered", report
    assert report["question"] == question and report["answer"] and report["citations"]
    assert len(report["steps"]) == 3 and report["model_calls"] == 0
    digest = hashlib.sha256(json.dumps(report, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return {"id": job_id, "states_observed": history, "engine": report["engine"],
            "model_calls": report["model_calls"], "steps": len(report["steps"]),
            "citations": len(report["citations"]), "sha256": digest}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("base_url", nargs="?", default="http://127.0.0.1:8000")
    cli.add_argument("--existing", help="Verify the same report after a pod restart")
    args = cli.parse_args()
    print(json.dumps(smoke(args.base_url, args.existing), ensure_ascii=False, indent=2))
