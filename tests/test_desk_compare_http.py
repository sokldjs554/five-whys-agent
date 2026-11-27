"""The same citations shown in a comparison must survive the public job API."""
import time

from fastapi.testclient import TestClient

from fivewhys.api import create_app


def test_two_reports_are_individually_quoteable(tmp_path):
    question = "현재 주문 장애를 과거 커넥션 풀 고갈 보고서와 캐시 스탬피드 보고서와 비교해 주세요."
    with TestClient(create_app(desk_db=tmp_path/"jobs.db")) as client:
        response = client.post("/desk/jobs", json={"question":question})
        assert response.status_code == 202
        status_url = response.json()["status_url"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if client.get(status_url).json()["status"] not in {"queued", "running"}:
                break
            time.sleep(0.1)
        result = client.get(response.json()["result_url"])
        assert result.status_code == 200
        result = result.json()
        assert result["status"] == "answered", result["reason"]
        reports = [ref for ref in result["citations"] if ref["id"].startswith("doc:")]
        assert len(reports) == 2
        assert reports[0]["source"] != reports[1]["source"]
        for report in reports:
            assert f"[{report['id']}]" in result["answer"]
            reply = client.post(f"{status_url}/messages", json={"citation_id":report["id"]})
            assert reply.status_code == 201
            assert reply.json()["reply"] == report
