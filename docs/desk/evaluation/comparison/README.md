# 두 장애 보고서 비교 평가

이전 버전은 커넥션 풀 고갈과 캐시 스탬피드의 원인을 비교해 달라는 두 질문을 입구에서 거절했다. 현재 버전은 풀 고갈 보고서의 **인덱스 없는 customer_ref 쿼리**와 캐시 보고서의 **워밍 없는 재시작으로 DB 조회가 폭증한 과정**을 각각 해당 보고서에서 인용한다. 현재 주문 장애를 함께 묻는 경우에는 시드 42의 배포 v2.4.0과 장애 시간대 로그를 별도로 인용한다. [수정 전 동일 질문](before.json) · [최종 실행 원자료](after/local.jsonl)

| 버전·실행 모드 | 비교 답변 | 올바른 보류 | 전체 | 실제 모델 응답 수 | 시도한 MCP 도구 호출 |
|---|---:|---:|---:|---:|---:|
| 변경 전 · 규칙 | 0/18 | 6/12 | 6/30 | 0 | 0 |
| 변경 전 · Qwen 설정 | 0/18 | 6/12 | 6/30 | 0 | 0 |
| 변경 후 · 규칙 | 18/18 | 12/12 | 30/30 | 0 | 72 |
| 변경 후 · Qwen | 18/18 | 12/12 | 30/30 | 24 | 72 |

질문은 총 10개로, 여섯 개는 답할 수 있고 네 개는 판단을 보류해야 한다. 각각 세 번 실행했다. 기존 평가에서 실패한 질문 2개와 별도로, 구현 확정 전에 한국어·영어 질문 8개와 정답을 고정했다. 질문 수와 실행 횟수를 구별했다. 같은 코퍼스와 같은 질문의 반복이므로 새로운 사건 전반의 정확도를 추정하는 수치로 사용할 수 없다. [평가 질문과 정답](cases.json) · [자료·질문 SHA-256](freeze.json)

## 어떤 근거를 확인했나

- **기존 실패 재현**. `hold-03`과 `challenge-05`는 원래 질문, 문서 정답, 배포 버전, 인용 및 용어 조건으로 다시 채점했다. 최초 버전에서는 각 모드 0/6, 수정 뒤에는 각 모드 6/6을 기록했다. 기존 평가 JSONL은 그대로 남아 있다. [원래 보류 세트](../heldout.json) · [원래 도전 세트](../challenge.json)
- **서로 다른 원인**. 커넥션 풀/캐시, TLS 인증서/디스크, DNS/OOM의 세 쌍을 사용했다. 두 도구 호출에서 얻은 문서 ID가 모두 맞아야 한다. 답변에서 각 인용 바로 앞에 있는 설명을 해당 문서에 지정한 원인 표현 두 묶음과 대조한다. 각 인용은 해당 MCP 응답의 본문·해시와 일치해야 하고, 본문은 원본 Markdown에서도 확인돼야 한다.
- **현재 장애와 과거 사례**. 질문에 현재 장애가 있으면 실제 주문 서비스의 v2.4.0 배포, customer_ref 변경, 장애 시간 내에서 관측한 관련 WARN/ERROR 로그를 확인한다. 보고서끼리만 비교하는 답에는 현재 로그나 배포 인용이 붙으면 실패다.
- **자료 부족**. 없는 보고서를 지목하거나 “두 이전 보고서”라고만 한 경우 인용 없는 보류를 요구한다. 현재 로그를 비우거나 특정 보고서 결과를 제거한 경우는 해당 장애 주입이 실제로 발생하고 `insufficient_evidence`로 끝나야 통과한다. 변경 전 버전은 모든 질문을 입구에서 거절해 두 장애 주입 지점에 도달하지 못했다.
- **실행 경로**. Qwen은 실제 HTTP 응답의 요청 ID와 토큰 수로 집계했다. `proposed_plan`은 플래너가 제안한 호출, `plan`은 이름이 확인된 문서와 요청 범위를 적용한 실행 목록이다. 두 보고서를 명시하면 프로그램이 각 문서의 근본 원인 섹션을 조회하고 인용문을 조립한다. 이 수치는 자유 질의에서 모델이 비교 문서를 스스로 발견하거나 차이를 독자적으로 추론하는 성능을 측정하지 않는다.

같은 Linux CPU 호스트에서 최종 Qwen 모드의 전체 조사 시간 p50/p95는 1.71/4.38초였고, 규칙 모드는 0.85/1.42초였다. Qwen은 입력 7,938토큰과 출력 747토큰을 사용했다. 범위 검사에서 끝난 요청을 포함한 관측값이다.

[변경 전 규칙 모드](before/offline.summary.json) · [변경 전 Qwen](before/local.summary.json) · [변경 후 규칙 모드](after/offline.summary.json) · [변경 후 Qwen](after/local.summary.json) · [모든 규칙 실행](after/offline.jsonl) · [모든 Qwen 실행](after/local.jsonl)

## Claude 실행과 전체 문서 조합

실패했던 한국어 질문 2개를 GitHub Actions에서도 각각 한 번 실행했다. Claude Haiku 5.5가 세 종류의 도구 호출을 제안했고, 조사기는 문서 검색 한 건을 두 건으로 나눴다. 각 질문에서 MCP 읽기 네 건이 성공했으며 보고서 두 건·로그·배포 인용을 원문과 대조했다. 과거 채점기의 `tool_selection_exact`는 실제 계획에 같은 도구 이름이 두 번 들어가면 false를 기록한다. 이 비교에서는 `proposed_plan`에서 세 도구 종류를, `steps`에서 두 개의 서로 다른 문서 ID를 별도로 확인한다. [실제 실행과 채점 원본](claude-actions.json) · [실행한 커밋](https://github.com/sokldjs554/five-whys-agent/tree/3b2f3eeffe19454a11e6fd393b57fbd4eab0470c) · [키 없는 공개 재생](https://sokldjs554.github.io/five-whys-agent/desk/?run=claude-hold-03)

제목을 정확히 제공한 경우의 문서 매칭은 자료 9건의 모든 조합으로도 점검했다. 규칙 계획기에서 36쌍을 각각 새 MCP 세션으로 실행한 결과, 모두 정확한 두 문서와 원문 해시를 인용했다. 자연어 표현의 일반화는 앞의 질문 세트로 별도 확인했다. [36개 결과](title-pairs.json) · [재현 스크립트](../../../../scripts/check_report_pairs.py) · [실제 REST 후속 인용 조회](http.json)

## 재현

저장소 루트에서 의존성을 설치하고, 로컬 모델 모드에서는 먼저 Qwen 서버를 실행한다. 매 질문은 새 stdio 세션을 열며 결과를 캐시하지 않는다. 수정 전 기준은 커밋 `fd8713b35d7d61492293fed204d906320cc84eb5`이다. [Qwen 서버 실행](../../local-model.md) · [평가 코드](../../../../scripts/evaluate_comparison.py)

```bash
python -m pip install -e .
python scripts/evaluate_comparison.py --mode offline --output-dir /tmp/desk-compare-offline
python scripts/evaluate_comparison.py --mode local --output-dir /tmp/desk-compare-qwen

mkdir -p /tmp/desk-compare-before
git archive fd8713b35d7d61492293fed204d906320cc84eb5 | tar -x -C /tmp/desk-compare-before
python scripts/evaluate_comparison.py --source-root /tmp/desk-compare-before --mode offline --output-dir /tmp/desk-before-runs
```
