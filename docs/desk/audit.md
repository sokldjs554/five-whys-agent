# GenOS 지원 프로젝트 최종 점검

주문 서비스 장애를 신고받은 운영자가 배포·로그·과거 보고서를 대조하고, 원인 후보를 인용 원문까지 확인하는 업무를 점검했다. 비교할 보고서 두 건을 지정한 질문과 최근 배포를 과거 보고서 한 건과 대조하는 질문은 서로 다른 조사 계획이 필요하다. 처음에는 후자를 보류하는 회귀가 있었다. 질문의 ‘최근 배포’ 표현을 현재 사건으로 인식하도록 고치고 두 경로를 함께 재검증했다. [수정 및 회귀 테스트](https://github.com/sokldjs554/five-whys-agent/commit/d7675e138fd7d222f186da1034aa071d568c246a) · [수정 전 실행](evaluation/reaudit/before/)

## 같은 입력으로 확인한 결과

각 질문을 모드별로 세 번 실행했다. 기존에 고정한 세트이므로 이번 실행은 회귀 평가다. 두 세트에는 겹치는 질문이 있다. 모든 수치는 각 세트 안의 실행을 분모로 계산했다.

| 수정 후 평가 | 근거를 갖춘 답 | 올바른 보류 | 전체 | 실제 모델 호출 | 실행 원본과 측정 환경 |
|---|---:|---:|---:|---:|---|
| 보고서 비교 10문항 · 규칙 | 18/18 | 12/12 | 30/30 | 0 | [집계](evaluation/reaudit/comparison/offline.summary.json) · [원본](evaluation/reaudit/comparison/offline.jsonl) |
| 보고서 비교 10문항 · Qwen | 18/18 | 12/12 | 30/30 | 24 | [집계](evaluation/reaudit/comparison/local.summary.json) · [원본](evaluation/reaudit/comparison/local.jsonl) |
| 일반 조사 포함 7문항 · 규칙 | 15/15 | 6/6 | 21/21 | 0 | [집계](evaluation/reaudit/challenge/offline-challenge-summary.json) · [원본](evaluation/reaudit/challenge/offline-challenge.jsonl) |
| 일반 조사 포함 7문항 · Qwen | 9/15 | 6/6 | 15/21 | 18 | [집계](evaluation/reaudit/challenge/local-challenge-summary.json) · [원본](evaluation/reaudit/challenge/local-challenge.jsonl) |

Qwen은 게이트웨이 504를 조사할 때 문서 검색어로 디스크 부족을 선택했다. 영어 간접 표현에서는 로그 검색어로 다른 서비스명을 골랐다. 두 질문 모두 답할 자료가 있었지만 세 번씩 보류됐다. 도구 실행은 57/57 성공했어도 관련 문서 회수는 15/18이었다. 규칙과 Qwen 모두 두 보고서의 원문 인용을 조립할 때 같은 Python 검증기를 사용한다. 최초 비교 구현 전후의 성능, 질문 동결 시점과 실패 주입 조건을 별도로 보존했다. [비교 기준선과 별도 문항](evaluation/comparison/) · [최초 개발·별도 평가 이력](evaluation/README.md)

수정 커밋에서 Claude 비교도 다시 실행했다. 기존 실패 질문 두 개가 각각 HTTP 200을 반환했고 MCP 호출 네 건씩 거쳐 검증 답변을 생성했다. 이 재실행은 CI 로그로 확인했다. [실행과 단계별 로그](https://github.com/sokldjs554/five-whys-agent/actions/runs/45959623896) · [두 질문의 결과](evaluation/reaudit/claude-ci.txt) · [이전 비교 실행의 전체 인용 원본](evaluation/comparison/claude-actions.json)

## 면접관이 확인할 수 있는 범위

| 요구사항 | 확인 근거 |
|---|---|
| 공고와 기술 선택 | 제논 원문의 업무 3개, 자격 요건 8개, 우대 사항 6개를 대조했다. Python·LangGraph·stdio MCP·REST의 역할, 로컬 Redis·Kubernetes 복구, CPU 모델·임베딩 서빙의 측정 조건이 있다. 학적과 지원자 본인의 재현은 별도 확인 항목이다. [공고 대조표](requirements.md) · [저장소 선정·재사용과 라이선스](selection.md) |
| 업무 흐름과 예외 | 로컬 웹에서 접수·대기·결과 조회·인용 후속 조회까지 실행했다. 범위 밖 질문, 도구 인자 오류, 시간 초과, 외부 오류, 빈 검색 결과, 근거 충돌을 다룬다. [구조와 실행 명령](README.md) · [실패 평가](evaluation/README.md) · [수정 후 CI](https://github.com/sokldjs554/five-whys-agent/actions/runs/45959416489) |
| 유사 제품과 설계 | 국내외 오픈소스 4개·상용 서비스 2개의 구현 또는 공개 자료를 비교했다. 별도로 제품 화면 7종에서 인용 이동과 호출 상세 표시 방식을 조사했다. 데스크는 밝은 바탕과 보라색을 쓰며 기록 선택을 대화상자로 연다. [프로젝트·평가 비교](related-work.md) · [화면 조사와 적용 이유](design.md) |
| 공개 데모와 버전 | Pages 버전 b4a6df1의 index.html·app.js·style.css·runs.json이 이번에 검사한 소스와 바이트 단위로 같았다. 로그인 없는 공개 Chromium 1440px·390px에서 각각 네 개의 인용과 도구 단계를 보고 두 문서의 원문을 열었다. 재생 기록은 생성 당시 리비전을 보존한다. [공개 비교](https://sokldjs554.github.io/five-whys-agent/desk/?run=claude-hold-03) · [배포 이력·캡처](release.md) |
| 빈 화면·로딩·오류·긴 결과 | Chromium에서 저장 기록 11건을 대상으로 다섯 화면 폭, 검색·보류 필터, 긴 출력과 원문 이동, 빈 목록, 데이터 로딩 실패 후 재시도, 로컬 실시간 Qwen 조사를 확인했다. [실행 결과](evaluation/reaudit/browser.txt) · [브라우저 검사 코드](check_ui.py) |
| 트래픽과 기여 범위 | 단일 워커 로컬 부하 실험에서 42건 중 32건 접수, 10건 HTTP 429, 완료 지연 p95 19.32초를 기록했다. 실사용 트래픽과 장기 운영 경험은 미검증이다. 이번 구현·평가·수정·브라우저 검사는 Codex가 수행했다. 지원자가 직접 제출한 기존 작업과 이번 버전의 본인 재현 여부를 따로 기록했다. [부하 원자료와 다음 실험](load/) · [수행자 구분](requirements.md) |

## 재현

저장소 루트에서 프로젝트 환경을 설치한다. Qwen 평가에는 로컬 모델 서버가 필요하다. Redis 통합 테스트는 별도의 테스트 Redis 주소를 DESK_TEST_REDIS_URL로 지정한다. 이번 로컬 전체 테스트는 전용 Redis와 함께 132개를 통과했다. [설치와 API 실행](README.md) · [모델 실행](local-model.md)

```bash
python -m pytest -o addopts='' -q
python scripts/desk_eval.py --mode offline --split challenge --repeats 3 --results-dir /tmp/desk-challenge
python scripts/desk_eval.py --mode local --split challenge --repeats 3 --results-dir /tmp/desk-challenge
python scripts/evaluate_comparison.py --mode offline --output-dir /tmp/desk-comparison
python scripts/evaluate_comparison.py --mode local --output-dir /tmp/desk-comparison
```
