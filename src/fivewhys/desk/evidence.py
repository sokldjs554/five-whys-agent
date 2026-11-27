"""Check agreement and generate statements directly from the retrieved records."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from fivewhys.desk.mcp_tools import DeskError
from fivewhys.scenarios.generator import BASE_TIME, BASELINE_MINUTES, INCIDENT_MINUTES

WINDOW_START = BASE_TIME + timedelta(minutes=BASELINE_MINUTES)
WINDOW_END = WINDOW_START + timedelta(minutes=INCIDENT_MINUTES)
# Route familiar diagnosis requests by subject and intent. Explicitly exclude other
# operational questions whose requested fact cannot be established from these sources.
_SUBJECT = re.compile(
    r"주문|오더|orders?\b|order-service|hikari|커넥션|연결\s*풀|connection\s*pool|"
    r"db\s*(pool|풀)|customer_ref|504|db_pool_exhaustion", re.I)
_INTENT = re.compile(
    r"장애|근거|증거|원인|배포|비교|문서|로그|타임아웃|고갈|이력|변경|유사|오류|왜|실패|지연|"
    r"진단|조사|분석|문제|무슨\s*일|incident|cause|evidence|deploy|change|timeout|timed out|"
    r"exhaust|logs?\b|diagnos|compar|postmortem|why|fail|investigat|went wrong", re.I)
_UNSUPPORTED = re.compile(
    r"매출|손실|금액|비용|급여|고객\s*수|사용자\s*수|몇\s*(건|명|퍼센트)|오류율|장애율|"
    r"날씨|개인정보|비밀번호|연락처|담당자|이메일|리전|지역|복구|복원|해결\s*시간|"
    r"인증서|쿠버네티스|메모리|디스크|캐시|결제|스탬피드|디엔에스|[\u3400-\u9fff]|"
    r"revenue|loss|how (many|much)|error rate|percent|password|credential|email|weather|"
    r"region|country|recover|restor|resolution time|duration|issuer|certificate|kubernetes|"
    r"\b(?:k8s|dns|tls|redis|kafka|oom|cache|payment|disk|memory)\b", re.I)
_MULTI_REPORT = re.compile(
    r"(?:여러|각각|양쪽|두|세|모든|전체|복수|[2-9])\s*(?:개의?\s*)?(?:장애\s*)?(?:문서|사례|보고서)|"
    r"(?:문서|사례|보고서)\s*(?:두|세|[2-9]|각각)|"
    r"\b(?:both|two|multiple|all|each)\s+(?:(?:historical|past|incident)\s+)*(?:reports?|documents?|postmortems?|cases?)",
    re.I)
_SERVICE = re.compile(r"\b[a-z]+(?:-[a-z]+)*-service\b", re.I)
_VERSION = re.compile(r"v\d+\.\d+(?:\.\d+)?", re.I)


def in_scope(question: str) -> bool:
    if not isinstance(question, str) or not 0 < len(question.strip()) <= 800:
        return False
    return bool(
        _SUBJECT.search(question) and _INTENT.search(question)
        and not _UNSUPPORTED.search(question) and not _MULTI_REPORT.search(question)
        and all(name.lower() == "order-service" for name in _SERVICE.findall(question))
    )


def timestamp(row):
    try:
        ts = datetime.fromisoformat(row["ts"])
        if ts.utcoffset() is None:
            raise ValueError("timezone required")
        return ts
    except ValueError as error:
        raise DeskError("invalid_result") from error


def unique_records(rows, key):
    records = {}
    for row in rows:
        identity = key(row)
        if identity in records and records[identity] != row:
            raise DeskError("conflict")
        records[identity] = row
    return list(records.values())


def log_observation(row) -> str | None:
    service, msg = row["service"], row["message"].lower()
    if row["level"] not in {"WARN", "ERROR", "FATAL"} or not WINDOW_START <= timestamp(row) <= WINDOW_END:
        return None
    if service == "order-service" and "hikaripool" in msg:
        if "not available" in msg and "timed out" in msg:
            return "주문 서비스가 DB 커넥션을 얻지 못해 요청이 타임아웃됐습니다."
        if "acquisition time" in msg and "exceeds" in msg:
            return "주문 서비스의 DB 커넥션 획득 시간이 경고 기준을 넘었습니다."
    if service == "order-service" and "sqltransientconnectionexception" in msg:
        return "주문 조회가 DB 연결 예외로 실패했습니다."
    if service == "mysql" and "slow query" in msg and "customer_ref" in msg:
        return "MySQL이 customer_ref 조건의 주문 조회를 슬로우 쿼리로 기록했습니다."
    if service == "api-gateway" and all(term in msg for term in ("order-service", "timeout", "504")):
        return "게이트웨이가 주문 서비스의 응답을 기다리다가 504를 반환했습니다."
    return None


_POOL = re.compile(r"hikaripool|connection pool|커넥션\s*풀|연결\s*풀", re.I)
_POOL_FAILURE = re.compile(
    r"(?:pool|풀)(?:이|이\s*|은|을|가|은\s*)?\s*(?:고갈|exhaust|was exhausted|is exhausted)|"
    r"exhaust(?:ed|ion of)\s+(?:the\s+)?(?:connection\s+)?pool|"
    r"connection is not available|커넥션을 얻지 못", re.I)
_QUERY_FAILURE = re.compile(r"풀스캔|full scan|slow query|슬로우\s*쿼리|인덱스\s*없|비인덱스", re.I)
_NEGATED = re.compile(
    r"(?:고갈|타임아웃)(?:이|은|되지|되지도)?\s*(?:않|없|아니)|"
    r"(?:no|not|never)\s+(?:pool\s+)?(?:exhaust|timed out)|ruled out", re.I)


def historical_quote(doc, log, deployment):
    # Check the text itself for both an overlapping entity and a failure mechanism.
    # Returned filenames, headings and number of retrieved chunks confer no support.
    text = doc["text"].removeprefix(doc["section"] + "\n")
    current = log["message"].lower()
    order_subject = "order-service" in text.lower() or "주문" in text
    shares_pool = "hikaripool" in current or "sqltransientconnectionexception" in current
    shares_query = "customer_ref" in deployment["description"].lower()
    for sentence in re.split(r"(?<=[.!?])\s+|\n(?=[-*0-9])", text):
        if _NEGATED.search(sentence):
            continue
        if shares_query and "customer_ref" in sentence.lower() and _QUERY_FAILURE.search(sentence):
            return sentence.strip()
        if (shares_pool or order_subject) and _POOL.search(sentence) and _POOL_FAILURE.search(sentence):
            return sentence.strip()
    return None


def verify(steps, question: str = ""):
    data = {step["tool"]: step["output"] for step in steps}
    changes = unique_records(data["list_change_events"], lambda r: r["id"])
    logs = unique_records(data["search_logs"], lambda r: r["id"])
    docs = unique_records(data["search_past_incidents"], lambda r: (r["doc"], r["section"], r["text"]))
    deployments = [
        row for row in changes
        if row["service"] == "order-service" and row["kind"] == "deploy"
        and BASE_TIME <= timestamp(row) <= WINDOW_START
    ]
    if len(deployments) > 1:
        raise DeskError("conflict")
    deployment = next((r for r in deployments if "customer_ref" in r["description"]), None)
    match = next(((r, msg) for r in logs if (msg := log_observation(r))), None)
    if not (deployment and match):
        raise DeskError("insufficient_evidence")
    requested_versions = {v.lower() for v in _VERSION.findall(question)}
    available_versions = {v.lower() for v in _VERSION.findall(deployment["description"])}
    if requested_versions - available_versions:
        raise DeskError("out_of_scope")
    log, symptom = match
    historical = next(((d, quote) for d in docs
                       if (quote := historical_quote(d, log, deployment))), None)
    if not historical:
        raise DeskError("insufficient_evidence")
    doc, quote = historical
    ref = hashlib.sha256(doc["text"].encode()).hexdigest()[:10]
    citations = [
        {"id": f"change:{deployment['id']}", "text": deployment["description"],
         "source": f"db_pool_exhaustion/deploys · {deployment['service']} · {deployment['ts']}"},
        {"id": f"log:{log['id']}", "text": log["message"],
         "source": f"db_pool_exhaustion/logs · {log['service']} · {log['ts']}"},
        {"id": f"doc:{doc['doc']}:{ref}", "text": doc["text"],
         "source": f"postmortems/{doc['doc']}.md · {doc['section']}"},
    ]
    observation = (f"{timestamp(deployment):%H:%M}의 변경 기록은 "
                   f"“{deployment['description']}”입니다 [{citations[0]['id']}]. "
                   f"{timestamp(log):%H:%M}에 {symptom.removesuffix('.')} [{citations[1]['id']}].")
    answer = (f"{observation}\n\n유사 장애 보고서의 ‘{doc['section']}’에는 "
              f"“{quote}”라고 기록돼 있습니다 [{citations[2]['id']}]. "
              "이번 장애에서는 이 배포로 바뀐 쿼리를 우선 원인 후보로 볼 수 있습니다.")
    return answer, citations
