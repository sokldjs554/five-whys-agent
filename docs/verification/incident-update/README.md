# 확장 백엔드 보완 및 검증 인계

**실제 Claude 조사는 미실행이다.** 공개 백엔드의 기존 기록과 로컬 PostgreSQL에서 이번 조건을 충족하는 작업을 확인하지 못했다. 이전 Claude 측정은 CLI에서 수행했다. 이번 실행 환경의 API와 워커에 Anthropic 자격 증명이 없었고, 수집기는 플랫폼팀 분석을 접수하기 전에 종료했다. 실제 작업 ID, 모델 응답, 인용, 토큰 사용량, 콜백 전후 호출 수는 미측정이다. [사전 점검 원자료](claude-preflight.json) · [Claude 실측 절차](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/claude/README.md)

확장판은 운영자가 지정한 단일 작업에 한해 공급자 응답 모델·ID와 제공된 사용량, 도구 선택·반환 근거, 최초 제출·수정·검증 결과를 PostgreSQL에 기록한다. 재전송 전후의 같은 작업 ID·분석 실행 횟수·결과 SHA-256·실제 호출 시도·수신기 응답을 대조하는 수집기를 추가했다. 13:20 배포, 14:00 이후 슬로우 쿼리, 연결 풀 대기의 순서를 원문으로 대조할 기준도 작성했다. 이번 사건에서 인덱스나 실행계획이 원인이었는지는 추가 자료가 필요하다. 이것은 사전 검토 기준이며 아직 이 사건에 대한 Claude의 판단은 없다. [실행 전 원문 기준](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/order-evidence-rubric.md)

## 두 번째 사건에서 확인한 점

인증서 만료 시드 42의 7문항에서 평균 Recall@4가 벡터 42.9%에서 그래프 결합 64.3%로 올랐다. 2문항 개선, 5문항 동일, 0문항 하락이었다. 그래프를 추가하면서 p50/p95 지연은 2.8/5.8 ms에서 5.2/11.9 ms로 늘었다. 두 방법 모두 결제 서비스의 캐시 세션 대체 경고를 놓쳤다. 두 방식 모두 상위 4개에 무관 배포를 반환한 문항이 없었다. 이 사건에는 조회 구간 안의 배포 자체가 없다. 규칙 기반 인과 질문 3건에서 배포를 원인으로 제시한 건수는 0건이었고, 주문팀은 직접 TLS 로그에 접근할 수 없어 판단을 보류했다.

주문 사건의 기존 7문항은 두 방식에서 각각 상위 후보 ID와 순서가 모두 유지됐다. 두 사건 평가는 기존 CLI의 5종 장애 RCA 평가와 별도로 Milvus·Neo4j 서버에 질의한 결과다. 각 질문의 허용 원문, 정답 순위, 두 사건에서 수집한 지연 표본 총 140개과 실패 사례를 공개했다. [두 사건 비교표](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/TWO_CASE_RETRIEVAL.md) · [측정 원본 JSON](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/two-case-retrieval.json)

## 실행 기록과 커밋

| 대상 | 기준 |
|---|---|
| 기존 공개 데모의 Scripted 기록 | 실행 기준 `4d01473`. 동일한 `src/`와 테스트를 공개한 [스냅샷 2848ab1](https://github.com/sokldjs554/five-whys-agent/tree/2848ab1e29d44421fdc38f1cbe249d8b65776985). |
| 두 번째 사건의 정답과 검색 | [검색 전 정답 고정 429993f](https://github.com/sokldjs554/five-whys-agent/commit/429993f446ca62299a26f6f5ada152b354ae38e5) · [실측 코드 a6cde05](https://github.com/sokldjs554/five-whys-agent/tree/a6cde056aac7a61c82594e7b9af5551c03cbdd6a) |
| 백엔드와 작업 수집기 | [테스트 커밋 b265ee8](https://github.com/sokldjs554/five-whys-agent/tree/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75) · [GitHub Actions 실행 로그와 JUnit 산출물](https://github.com/sokldjs554/five-whys-agent/actions/runs/45582146566) |
| 실제 Claude 기록 | 실행 커밋·작업 ID 미발급. 모델 대역으로 실행한 CI 결과와 Scripted 데모의 0 → 0은 실제 공급자 호출 측정값으로 사용하지 않았다. |
| 공개 화면 | [Pages 커밋 3763a55](https://github.com/sokldjs554/five-whys-agent/tree/3763a55ace8cbc2d92e3f109d66fc3dfe58f7bac) · [데모](https://sokldjs554.github.io/five-whys-agent/) · [Claude 상태 화면](https://sokldjs554.github.io/five-whys-agent/claude.html) |

## 자동 테스트 결과

GitHub 호스팅 러너에서 Compose를 새로 기동해 pytest **121개 통과, 실패·건너뜀 0개**를 확인했다. 51.58초가 걸렸고 Pika의 사용 중단 예정 경고가 9건 발생했다. 별도 수집기 단위 검사 6개도 통과했다. JUnit의 콜백 항목은 모델 대역에 대한 검증이다. [CI의 원본 JUnit](ci-pytest.xml) · [실행 로그](https://github.com/sokldjs554/five-whys-agent/actions/runs/45582146566)

## PC와 모바일 검증

로그인하지 않은 Chromium에서 1366×900과 390×844 화면으로 공개 URL을 직접 열었다. 두 크기 모두 주문팀·플랫폼팀을 바꿔 조사 기록 열기, 인용 원문 열고 닫기, 두 검색 순위와 그래프 경로의 원문 열기, 503 → 200 재전송 기록 열기를 확인했다. 새 링크로 이동했을 때 실제 Claude 화면의 미실행 상태와 다섯 섹션을 읽고 데모로 복귀했다. 새 화면은 정적 리소스만 GET으로 읽었다. 네트워크 검증에는 실행 환경의 HTTPS 프록시 인증서를 사용했다. [조작 결과 JSON](remote-ui-results.json) · [PC 첫 화면](desktop-landing.png) · [PC Claude 화면](desktop-claude.png) · [모바일 첫 화면](mobile-landing.png) · [모바일 Claude 화면](mobile-claude.png)

## 기여와 확인 범위

- 지원자는 장애 사례와 검증 기준을 정하고, 이전 전달본을 Codespaces에서 열어 화면 확인을 회신했다. 이번 보완에서는 실제 Claude의 판단과 검색기 결정을 구분하고, 같은 작업의 재전송·두 번째 장애·공개 자료를 검증하도록 요구했다. 이번 코드 변경을 지원자가 직접 작성했거나 새 CI와 캡처를 직접 리뷰했다는 기록은 아직 없다.
- Codex는 공개 브랜치와 실행 환경 확인, 관찰 코드·수집기·검증 테스트 구현, 정답표 사전 고정, 실서비스 검색 비교, GitHub 배포와 화면 조작 검증을 수행했다. Claude 자격 증명이 없는 상태에서 유료 실행값을 작성하지 않았다.
- 시나리오와 장애 로그는 합성 자료다. 실제 고객 장애 처리나 피피에스㈜ 수주 실적으로 확인된 항목은 없다.
