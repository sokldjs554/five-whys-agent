"""Resolve two named archival reports, then compare their independently read cause sections."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import re

from fivewhys.desk.evidence import current_evidence, current_log_query, document_citation, historical_quote, unsupported_current_subject
from fivewhys.desk.mcp_tools import DeskError, ScopedPastQuery
from fivewhys.pipeline import DEFAULT_POSTMORTEM_DIR

# Bilingual names identify subjects only. Report contents are retrieved via MCP.
SUBJECT_NAMES = {
    "rollback-failure": r"롤백\s*실패|rollback(?:\s+failure|\s+failed)?",
    "bad-config-rollout": r"잘못된\s*설정|설정\s*(?:전파|롤아웃)|게이트웨이\s*라우팅|bad[ -]config|config(?:uration)?[ -]rollout",
    "kafka-consumer-lag": r"kafka|카프카|consumer[ -]lag|컨슈머\s*랙",
    "dns-resolution": r"\bdns|디엔에스",
    "cache-stampede": r"cache[ -]stampede|캐시\s*(?:재시작|스탬피드)|스탬피드",
    "tls-cert-expiry": r"\btls|(?:(?:ssl|tls)\s*)?인증서\s*만료|cert(?:ificate)?[ -](?:expiry|expiration|expired)",
    "disk-full-logging": r"디스크\s*(?:고갈|가득|소진|용량)|로그\s*디스크|disk[ -](?:full|exhaustion)|log(?:ging)?[ -]disk",
    "payment-oom": r"payment[ -]service\s+oom|\boom|결제\s*(?:서비스\s*)?(?:메모리|oom)|out[ -]of[ -]memory|memory[ -]leak",
    "db-connection-pool": r"hikaripool|커넥션\s*풀|연결\s*풀|connection[ -]pool|db[ -]pool|db\s*풀",
}

_COMPARISON = re.compile(r"비교|차이|대조|각각|(?:어떻게|무엇이|뭐가|어디가|뭐가\s*어떻게)\s*(?:달|다르)|다른\s*점|compare|contrast|differ|versus|\bvs\.?\b|respectively", re.I)
_CURRENT = re.compile(r"현재|이번|지금|실시간|실제\s*(?:배포|로그|장애)|오늘|현\s*장애|"
                      r"(?:보입니다|관측됐|보였|관찰됐|발견됐|발생\s*중)|(?:주문|order-service)\s*장애에서|"
                      r"we(?:'re| are) seeing|we (?:see|observed)|shows? up in (?:our|the) logs|current|live\s+(?:log|change|incident)|today|ongoing|this\s+(?:incident|deployment)", re.I)
_REPORT = re.compile(r"보고서|문서|사례|포스트모템|postmortems?|reports?|documents?|cases?", re.I)
_PAIR = re.compile(r"(?:두|두세|2|여러)\s*(?:개의?\s*)?(?:서로\s*다른\s*)?(?:보고서|문서|사례)|"
                   r"(?:문서|보고서|사례)\s*(?:두|2)|\b(?:both|two|multiple)\s+(?:\w+\s+){0,2}(?:reports|postmortems|cases)", re.I)
# Cause comparison is supported; requests for monetary, personal, or operational
# measurements need facts beyond two cause sections.
_OTHER_FACT = re.compile(
    r"매출|손실|금액|비용|오류율|고객\s*수|사용자\s*수|복구\s*(?:시각|시간)|담당자|비밀번호|"
    r"리전|지역|연락처|이메일|revenue|loss|error\s*rate|how many|how much|credential|"
    r"duration|recover|restor|복구|대책|재발\s*방지|remedia|mitigat|password|personal data|region", re.I)
_SECTION = "근본 원인"
_NAME_HELP = "비교할 서로 다른 과거 장애 보고서 두 건의 주제, 제목 또는 날짜를 지정해 주세요."


@dataclass(frozen=True)
class NamedReport:
    doc: str
    title: str
    names: re.Pattern


@lru_cache(maxsize=1)
def report_catalog() -> tuple[NamedReport, ...]:
    reports = []
    for path in sorted(DEFAULT_POSTMORTEM_DIR.glob("*.md")):
        with path.open(encoding="utf-8") as stream:
            title = stream.readline().lstrip("# ").strip().removeprefix("장애 보고서: ")
        subject = path.stem[11:]
        names = [re.escape(path.stem), re.escape(path.stem[:10]), re.escape(title.split(" (")[0])]
        if subject in SUBJECT_NAMES:
            names.append(SUBJECT_NAMES[subject])
        reports.append(NamedReport(path.stem, title, re.compile("|".join(names), re.I)))
    return tuple(reports)


@dataclass(frozen=True)
class Comparison:
    reports: tuple[NamedReport, NamedReport]
    include_current: bool
    current_context: str


def resolve_comparison(question: str) -> Comparison | None:
    if not _COMPARISON.search(question):
        return None
    matches = sorted(
        ((match.start(), report) for report in report_catalog() if (match := report.names.search(question))),
        key=lambda item: item[0],
    )
    explicit_pair = _PAIR.search(question) or len(_REPORT.findall(question)) >= 2
    include_current = bool(_CURRENT.search(question))
    if len(matches) < 2:
        if matches and (explicit_pair or not include_current and _REPORT.search(question)
                        and re.search(r"\b(?:and|versus|vs)\b|(?:와|과)\s", question, re.I)):
            raise DeskError("insufficient_evidence", _NAME_HELP)
        if not matches and explicit_pair:
            raise DeskError("out_of_scope", _NAME_HELP)
        return None
    if len(matches) != 2:
        raise DeskError("insufficient_evidence", _NAME_HELP)
    if _OTHER_FACT.search(question):
        raise DeskError("out_of_scope")
    reports = (matches[0][1], matches[1][1])
    current_context = question
    for report in reports:
        current_context = report.names.sub(" ", current_context)
    if include_current and unsupported_current_subject(current_context):
        raise DeskError("out_of_scope")
    return Comparison(reports, include_current, current_context)


def expand_plan(base, comparison):
    calls = []
    for call in base:
        if call["tool"] == "search_past_incidents":
            for report in comparison.reports:
                args = ScopedPastQuery(query=call["input"]["query"], k=2, doc=report.doc, section=_SECTION)
                calls.append({"tool": call["tool"], "input": args.model_dump()})
        elif comparison.include_current and call["tool"] == "search_logs":
            # Restrict the current log read independently of archival topic names.
            # The provider's original log query remains visible in proposed_plan.
            calls.append({"tool": "search_logs", "input": current_log_query(comparison.current_context)})
        elif comparison.include_current:
            calls.append(call)
    return calls


def compare_evidence(steps, question, comparison):
    reads = [s for s in steps if s["tool"] == "search_past_incidents"]
    if len(reads) != 2:
        raise DeskError("insufficient_evidence")
    citations, causes = [], []
    for read, report in zip(reads, comparison.reports, strict=True):
        rows = read["output"]
        if not rows:
            raise DeskError("insufficient_evidence")
        if len(rows) != 1 or read["input"]["doc"] != report.doc:
            raise DeskError("conflict")
        row = rows[0]
        if row["doc"] != report.doc or row["section"] != _SECTION:
            raise DeskError("conflict")
        header, sep, cause = row["text"].partition("\n")
        if not sep or header.strip() != _SECTION or not cause.strip():
            raise DeskError("insufficient_evidence")
        citations.append({**document_citation(row), "title": report.title})
        causes.append(cause.strip())
    if " ".join(causes[0].split()) == " ".join(causes[1].split()):
        raise DeskError("conflict")
    # Include the causal chain, not just the opening sentence: a report can name
    # the missing safeguard first and explain how it affected the database later.
    answer = (
        f"두 보고서가 설명하는 장애의 발단과 전파 과정은 다음과 같습니다.\n\n"
        f"{comparison.reports[0].title}\n{causes[0]} [{citations[0]['id']}]\n\n"
        f"{comparison.reports[1].title}\n{causes[1]} [{citations[1]['id']}]"
    )
    if all(re.search(r"(?:DB\s*)?커넥션.{0,55}고갈", cause, re.S) for cause in causes):
        answer += (f" 두 장애 모두 DB 커넥션 고갈로 이어졌습니다 "
                   f"[{citations[0]['id']}] [{citations[1]['id']}].")
    if comparison.include_current:
        data = {s["tool"]: s["output"] for s in steps if s["tool"] != "search_past_incidents"}
        deployment, log, observation, current_citations = current_evidence(data, comparison.current_context)
        answer += f"\n\n현재 주문 장애 — {observation} 현재 원인 후보는 이 배포의 쿼리 변경입니다."
        for read, ref in zip(reads, citations, strict=True):
            passage = read["output"][0]
            if historical_quote(passage, log, deployment) and "customer_ref" in passage["text"].lower():
                answer += (f" 현재 변경 기록과 ‘{ref['title']}’의 원인 구절에는 "
                           f"customer_ref 조건이 함께 등장합니다 [{current_citations[0]['id']}] [{ref['id']}].")
        citations.extend(current_citations)
    return answer, citations
