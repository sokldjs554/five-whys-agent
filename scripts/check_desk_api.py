"""Exercise a running local desk through HTTP and optionally save the full responses."""
import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen


def fetch(url, body=None):
    request = Request(url, headers={"Content-Type":"application/json"},
                      data=None if body is None else json.dumps(body).encode())
    with urlopen(request, timeout=15) as response:
        return response.status, json.load(response)


def run(base, engine, question):
    start = time.monotonic()
    code, accepted = fetch(f"{base}/desk/jobs", {"question":question, "engine":engine})
    if code != 202:
        raise RuntimeError(f"POST /desk/jobs returned {code}")
    url = base + accepted["status_url"]
    history = [accepted["status"]]
    while time.monotonic() - start < 190:
        _, status = fetch(url)
        state = status["status"]
        if state != history[-1]:
            history.append(state)
        if state in {"completed", "failed", "withheld"}:
            break
        time.sleep(.1)
    else:
        raise TimeoutError("Job did not reach a terminal state")
    _, result = fetch(base + accepted["result_url"])
    citations = result["citations"]
    if citations:
        _, reply = fetch(url+"/messages", {"citation_id":citations[0]["id"]})
        _, messages = fetch(url+"/messages")
        if reply not in messages or reply["reply"] != citations[0]:
            raise ValueError("Stored follow-up did not match cited evidence")
    else:
        _, messages = fetch(url+"/messages")
    return dict(accepted=accepted, status=status, states_observed=history, result=result,
                followups=messages, elapsed_ms=round((time.monotonic()-start)*1000,1))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--engine", choices=["rules","local"], default="rules")
    parser.add_argument("--question", default="주문 서비스의 DB 연결 풀 오류와 관련된 배포를 조사해 줘")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = run(args.base.rstrip("/"),args.engine,args.question)
    if args.output:
        args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2)+"\n")
    print(data["states_observed"], data["result"]["reason"], len(data["result"]["citations"]))
