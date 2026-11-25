# 확장 백엔드 보완 및 검증 인계

**플랫폼팀 실제 Claude 조사와 동일 작업 콜백 복구를 확인했다.** 공개 데모에서 한 건의 저장된 실행을 재생한다. 모델 ID는 `claude-sonnet-5-5`, 실행 소스는 `b265ee8`, 작업 ID는 `e09c4226-20bf-462f-a673-c5dab75a9f7d`이다. 클라이언트가 HTTP 202를 받은 뒤 워커가 로그 4건과 배포 1건을 모델에 반환했다. 보고서 도구는 0건을 반환했다. 모델이 제출한 첫 가설은 인용 검증을 통과했다. [공개 기록](https://sokldjs554.github.io/five-whys-agent/claude.html) · [실제 실행](https://github.com/sokldjs554/five-whys-agent/actions/runs/45585656133) · [원자료·전후 표](https://github.com/sokldjs554/five-whys-agent/tree/7db48acd6a6a2b6e1bb4e34f0c5730a523e456ec/docs/verification/claude/runs/e09c4226-20bf-462f-a673-c5dab75a9f7d)

13:20에 주문 조회에 customer_ref 조건을 추가했고, 14:00부터 같은 조건으로 느린 SQL이 기록됐다. 뒤이어 풀 대기와 504가 관측됐다. 모델은 이를 가장 유력한 후보로 두고 배포 직후 성능과 실행계획, 같은 요청 경로인지에 대한 판단을 유보했다. Redis 재시작 사례는 최초 벡터 검색 1위에서 그래프 검색기가 제외했다. 모델의 최종 보고서는 Redis를 언급하지 않았다. 재전송 503 → 200 전후에 작업 ID와 저장 결과 SHA-256이 같았고, 분석 1회·모델 호출 2회가 유지됐다. [사전 원문 대조 기준](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/order-evidence-rubric.md) · [최초 로컬 사전 점검](claude-preflight.json)

## 두 번째 사건에서 확인한 점

인증서 만료 시드 42의 7문항에서 평균 Recall@4가 벡터 42.9%에서 그래프 결합 64.3%로 올랐다. 2문항 개선, 5문항 동일, 0문항 하락이었다. 그래프를 추가하면서 p50/p95 지연은 2.8/5.8 ms에서 5.2/11.9 ms로 늘었다. 두 방법 모두 결제 서비스의 캐시 세션 대체 경고를 놓쳤다. 두 방식 모두 상위 4개에 무관 배포를 반환한 문항이 없었다. 이 사건에는 조회 구간 안의 배포 자체가 없다. 규칙 기반 인과 질문 3건에서 배포를 원인으로 제시한 건수는 0건이었고, 주문팀은 직접 TLS 로그에 접근할 수 없어 판단을 보류했다.

주문 사건의 기존 7문항은 두 방식에서 각각 상위 후보 ID와 순서가 모두 유지됐다. 두 사건 평가는 기존 CLI의 5종 장애 RCA 평가와 별도로 Milvus·Neo4j 서버에 질의한 결과다. 각 질문의 허용 원문, 정답 순위, 두 사건에서 수집한 지연 표본 총 140개와 실패 사례를 공개했다. [두 사건 비교표](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/TWO_CASE_RETRIEVAL.md) · [측정 원본 JSON](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/two-case-retrieval.json)

## 실행 기록과 커밋

| 대상 | 기준 |
|---|---|
| 기존 공개 데모의 Scripted 기록 | 실행 기준 `4d01473`. 동일한 `src/`와 테스트를 공개한 [스냅샷 2848ab1](https://github.com/sokldjs554/five-whys-agent/tree/2848ab1e29d44421fdc38f1cbe249d8b65776985). |
| 두 번째 사건의 정답과 검색 | [검색 전 정답 고정 429993f](https://github.com/sokldjs554/five-whys-agent/commit/429993f446ca62299a26f6f5ada152b354ae38e5) · [실측 코드 a6cde05](https://github.com/sokldjs554/five-whys-agent/tree/a6cde056aac7a61c82594e7b9af5551c03cbdd6a) |
| 백엔드와 작업 수집기 | [테스트 커밋 b265ee8](https://github.com/sokldjs554/five-whys-agent/tree/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75) · [GitHub Actions 실행 로그와 JUnit 산출물](https://github.com/sokldjs554/five-whys-agent/actions/runs/45582146566) |
| 실제 Claude 기록 | [실행 커밋 b265ee8](https://github.com/sokldjs554/five-whys-agent/tree/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75) · [원자료 커밋 7db48ac](https://github.com/sokldjs554/five-whys-agent/tree/7db48acd6a6a2b6e1bb4e34f0c5730a523e456ec/docs/verification/claude/runs/e09c4226-20bf-462f-a673-c5dab75a9f7d) · [수동 실행 워크플로](https://github.com/sokldjs554/five-whys-agent/blob/157ce276a98aa45a23c233a470327bd3d3b68a3a/.github/workflows/claude-investigation.yml) |
| 공개 화면 | [Pages 커밋 a19f7a9](https://github.com/sokldjs554/five-whys-agent/tree/a19f7a9112789bba7f26a3a56103c7ace48da023) · [데모](https://sokldjs554.github.io/five-whys-agent/) · [Claude 재생 화면](https://sokldjs554.github.io/five-whys-agent/claude.html) |

## 자동 테스트 결과

원자료를 포함한 최종 백엔드 커밋 `7db48ac`에서 GitHub 호스팅 러너로 Compose를 새로 기동해 pytest **121개 통과, 실패·건너뜀 0개**를 확인했다. 50.70초가 걸렸고 Pika의 사용 중단 예정 경고가 9건 발생했다. 별도 수집기 단위 검사 6개도 통과했다. JUnit의 콜백 항목은 모델 대역에 대한 검증이다. [CI의 원본 JUnit](ci-pytest.xml) · [실행 로그](https://github.com/sokldjs554/five-whys-agent/actions/runs/45586350064)

## PC와 모바일 검증

로그인하지 않은 Chromium에서 1366×900과 390×844 화면으로 공개 URL을 직접 열었다. 두 크기 모두 주문팀·플랫폼팀을 바꿔 조사 기록 열기, 인용 원문 열고 닫기, 두 검색 순위와 그래프 경로의 원문 열기, 503 → 200 재전송 기록 열기를 확인했다. 새 링크로 이동했을 때 실제 Claude 기록의 다섯 섹션을 읽고 모델의 검색어와 배포 원문을 펼쳤으며 같은 작업 ID·결과 해시와 전후 분석 및 호출 횟수를 확인한 뒤 데모로 복귀했다. 새 화면은 정적 리소스만 GET으로 읽었다. 네트워크 검증에는 실행 환경의 HTTPS 프록시 인증서를 사용했다. [조작 결과 JSON](remote-ui-results.json) · [PC 첫 화면](desktop-landing.png) · [PC Claude 화면](desktop-claude.png) · [모바일 첫 화면](mobile-landing.png) · [모바일 Claude 화면](mobile-claude.png)

## 기여와 확인 범위

- 지원자는 장애 사례와 검증 기준을 정하고, 이전 전달본을 Codespaces에서 열어 화면 확인을 회신했다. 이번 보완에서는 실제 Claude의 판단과 검색기 결정을 구분하고, 같은 작업의 재전송·두 번째 장애·공개 자료를 검증하도록 요구했다. 이번 코드 변경을 지원자가 직접 작성했거나 새 CI와 캡처를 직접 리뷰했다는 기록은 없다. 지원자가 GitHub Actions에 Anthropic 시크릿을 등록했고, 러너에서 인증이 성공했다.
- Codex는 공개 브랜치와 실행 환경 확인, 관찰 코드·수집기·검증 테스트 구현, 정답표 사전 고정, 실서비스 검색 비교, GitHub 배포와 화면 조작 검증을 수행했다. 이번에는 GitHub Actions에서 플랫폼팀 실제 Claude 조사 한 건을 실행하고 원자료 해시, 최종 인용, 콜백 복구, 공개 재생 화면을 검증했다.
- 시나리오와 장애 로그는 합성 자료다. 실제 고객 장애 처리나 피피에스㈜ 수주 실적으로 확인된 항목은 없다.
