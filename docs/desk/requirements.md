# GenOS AI Engineer 공고와 구현 근거

제논의 **GenOS AI Engineer (전환형인턴)** 공고를 2026-11-27 공식 채용 페이지에서 다시 읽었다. 아래 첫 열은 업무 3개, 자격 요건 8개, 우대 사항 6개의 원문이다. 공고는 우대 사항을 필수 요건과 구분한다. 이 대조표는 개인 프로젝트의 실행 범위와 지원자 확인이 필요한 항목을 함께 표시한다. [제논 공식 공고](https://genon.ninehire.site/job_posting/uIRXtx5v)

## 주요 업무

| 공고 원문 | 대응하는 결과와 확인 범위 |
|---|---|
| 생성형 AI 플랫폼(GenOS) 구축 및 운영 프로젝트 수행 | 소규모 조사 서비스를 구현했다. 요청을 SQLite에 저장한 뒤 HTTP 202로 작업 ID를 돌려주며 상태·결과를 각각 조회한다. 워커 종료·재기동 시의 상태 전이는 테스트에 있다. 제논의 GenOS 자체 구축·고객사 운영 경험은 확인되지 않았다. [REST 경계](../../src/fivewhys/desk/routes.py) · [작업 수명과 실패 테스트](../../tests/test_desk_jobs.py) |
| LLM 기반 에이전트 개발 프로젝트 수행 | Qwen이 실제로 선택하는 부분은 첫 도구와 두 검색어다. 세 종류의 증거를 확인하는 정책, 인자 검사, 인용을 붙인 최종 응답은 Python 코드가 담당한다. 데스크의 실제 Claude 실행에서는 세 종류의 도구를 제안했고, 조사기는 비교 대상 두 문서를 각각 검색해 현재 배포·로그와 함께 총 네 번 호출했다. [Claude 비교 원본](evaluation/comparison/claude-actions.json) [이번 모델 실행](evaluation/local-heldout.jsonl) · [로컬 모델 설정](local-model.md) · [기존 Claude 실행](https://github.com/sokldjs554/five-whys-agent/tree/f8c8e20e848b568b9a1bca9a25168758323b14c2/docs/verification/claude/runs/e09c4226-20bf-462f-a673-c5dab75a9f7d) |
| 생성형 AI 기술 구현 및 PoC 수행 | 같은 고정 질문에 규칙 계획과 로컬 모델 계획을 각각 적용했다. 검색 정답 포함 여부, 도구 실행, 근거 있는 답, 올바른 보류를 따로 집계한다. 최초 보류 세트에서 모델은 보류해야 하는 7문항을 세 번씩 올바르게 보류했으나 답할 수 있는 3문항에서는 세 번 모두 근거 답변에 실패했다. [버전별 결과·실패 분석](evaluation/README.md) [평가 입력](evaluation/heldout.json) · [규칙 결과](evaluation/offline-heldout-summary.json) · [모델 결과](evaluation/local-heldout-summary.json) |

## 자격 요건

| 공고 원문 | 제출 근거와 판단의 한계 |
|---|---|
| 학사 이상 (2027년 2월 졸업예정자 지원 가능) | **본인 확인 필요.** 학위·졸업(예정)일은 저장소에서 추정하지 않는다. 지원서의 실제 학적 정보로 확인할 항목이다. |
| 관련 전공 또는 그에 준하는 개발 경험(부트캠프, 프로젝트 등) 보유자 | 공고가 허용하는 프로젝트 경험에 대한 증빙은 있다. 전공·부트캠프 이력 및 채용사의 동등성 판단은 별도다. [프로젝트 선정 근거](selection.md) · [본인 제출 기록](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/artifacts/author-diagnostic-test-20261111/submission.json) |
| LLM 및 RAG 관련 기술에 대한 기본 지식을 갖춘 분 | 질문을 검색어로 바꾸는 모델 경로, 검색 구절의 원문 ID, 관련 없는 결과의 기권을 코드·실패 기록에서 확인할 수 있다. 기존 검색기는 키워드 순위와 벡터 순위를 RRF로 합친다. [계획 어댑터](../../src/fivewhys/desk/local_model.py) · [근거 검사](../../src/fivewhys/desk/evidence.py) · [RRF 구현](https://github.com/sokldjs554/five-whys-agent/blob/9dda870837334bc2b0cdc29a30049920028559d8/src/fivewhys/rag/retriever.py) |
| Python 등 1개 이상의 프로그래밍 언어로 직접 코드를 작성·디버깅할 수 있는 분 | 기존 QuarterGuard에서 지원자가 제출한 기간 진단 설명 변경·회귀 테스트가 기록돼 있다. 같은 3분기 매출 자료를 전분기 비교로 넘기면 보류하고, 전년 동기로 넘기면 17.3491%를 허용한다. 이 사례를 직접 작성·디버깅 근거로 한정한다. [구현 제출](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/docs/code-review-kit/04-period-diagnostic-author-20261110.md) · [테스트 제출](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/docs/code-review-kit/05-period-diagnostic-test-20261111.md) · [전년·전분기 입력](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/tests/test_my_period_review.py) |
| LangChain·LangGraph 등 주요 AI 프레임워크로 에이전트를 개발해 본 경험이 있는 분 | 신규 구현의 LangGraph `StateGraph`가 계획·읽기·검증·종료 분기를 실행한다. 기존 확장판은 LangChain의 검색기 어댑터를 Milvus·Neo4j에 연결한다. 구현과 실행은 연결된 코드·테스트에서 확인할 수 있다. [그래프 코드](../../src/fivewhys/desk/engine.py) · [MCP 통합 테스트](../../tests/test_desk_engine.py) · [기존 프레임워크 사용](https://github.com/sokldjs554/five-whys-agent/blob/f8c8e20e848b568b9a1bca9a25168758323b14c2/src/fivewhys/investigation/retrieval.py) |
| AI 코딩 도구가 생성한 코드의 정확성을 검토하고 테스트로 검증할 수 있는 분 | 기존 QuarterGuard에는 저장된 진단 결과와 실제 도구 실행 이력을 혼동하는 문제를 구분한 지원자 테스트가 있다. 신규 코드의 회귀 테스트는 허용 목록 밖 계획·형식 오류·시간 초과를 주입해 동작을 검사한다. 기존 제출 기록과 신규 코드의 검증 범위를 구분한다. [기존 제출 기록](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/artifacts/author-diagnostic-test-20261111/submission.json) · [그래프 실패 검사](../../tests/test_desk_engine.py) |
| Tool Calling, MCP 등 에이전트 동작 원리와 연동 방식에 대한 이해가 있는 분 | MCP 클라이언트가 stdio 서버를 시작해 초기화하고 도구 목록을 탐색한다. 서버가 제공하는 스키마와 조사 정책으로 모델의 제안을 제한한 뒤 도구를 호출하고 결과를 검증한다. Qwen은 제한된 JSON 계획을 생성하고 Claude는 네이티브 도구 호출을 제안한다. 두 모델이 제안한 계획과 실제 호출을 각각 기록한다. [데스크의 Claude 실행](evaluation/comparison/claude-actions.json) [MCP 클라이언트](../../src/fivewhys/desk/mcp_tools.py) · [모델 계획](../../src/fivewhys/desk/local_model.py) · [Claude 도구 호출](https://github.com/sokldjs554/five-whys-agent/blob/f8c8e20e848b568b9a1bca9a25168758323b14c2/docs/verification/claude/runs/e09c4226-20bf-462f-a673-c5dab75a9f7d/result.body.json) |
| HTTP/REST API 통신에 대한 기본적인 이해가 있는 분 | 생성·상태 조회·결과 조회를 구분하고 작업 ID와 실패 상태를 전달한다. 로컬 추론 서버와 임베딩 서버도 HTTP로 연결한다. [FastAPI 라우트](../../src/fivewhys/desk/routes.py) · [응답 테스트](../../tests/test_desk_jobs.py) · [임베딩 서비스](../../src/fivewhys/desk/embedding_service.py) |

## 우대 사항

| 공고 원문 | 구현 또는 실험에서 확인할 수 있는 범위 |
|---|---|
| 에이전트의 실행 환경(컨텍스트 관리, 가드레일, 검증·평가 체계 등)을 설계하고 개선해 본 경험 | 사건 범위를 먼저 검사하고 읽기 전용 도구·검색 수·시간을 제한한다. 로그·배포·기존 문서가 불충분하거나 충돌하면 보류한다. 평가에서 보류 성공과 정답 도달 실패를 따로 확인할 수 있다. [실행 제어](../../src/fivewhys/desk/engine.py) · [증거 검증](../../src/fivewhys/desk/evidence.py) · [평가 원자료](evaluation/local-heldout.jsonl) |
| MCP 서버 개발 및 운영 경험 | 기존 Python 서버의 로그·변경·포스트모템 검색을 재사용한다. 실제 stdio 프로세스에서 목록 탐색·호출·종료를 확인할 수 있다. 검증된 범위는 프로젝트의 로컬/테스트 수명주기다. 상시 고객 서비스 운영 이력은 별도다. [기존 MCP 서버](https://github.com/sokldjs554/five-whys-agent/blob/9dda870837334bc2b0cdc29a30049920028559d8/src/fivewhys/mcp_server/server.py) · [실제 stdio 테스트](../../tests/test_desk_engine.py) |
| Redis, Kubernetes 실무 활용 경험 | 로컬 K3s에 단일 복제본·PVC 구성을 배포하고 ClusterIP HTTP 요청과 Redis hit/miss·TTL을 확인했다. Redis를 중단하고 API Pod를 교체한 뒤에도 SQLite에서 조회한 결과 해시가 일치했다. 기존 CareFlow의 Redis 실제 통합 CI와 InferenceRail의 kind HPA/KEDA 기록에서 각각의 실행 환경을 확인할 수 있다. 이 자료가 뒷받침하는 범위는 프로젝트 검증이다. [이번 로컬 클러스터 실행](ops.md) · [상태·해시 원자료](ops-evidence.json) · [캐시·폴백](../../src/fivewhys/desk/cache.py) · [Kubernetes 구성](../../deploy/desk/kubernetes.yaml) · [CareFlow CI](https://github.com/sokldjs554/careflow-backend/actions/runs/34066678637) · [kind 클러스터 기록](https://github.com/sokldjs554/inference-rail/blob/8a2c9a4400af176362b1ded0808bbc984c617112/docs/evidence/k8s-runtime-summary.json) |
| 벡터 검색 및 RAG 솔루션 구축 경험 | 기본값은 어휘 해싱과 키워드 검색이다. 선택한 HTTP 인코더 경로에서는 실제 다국어 MiniLM의 384차원 벡터를 계산한다. 기존 별도 확장판에서는 동일 문항에서 그래프 연결이 도움이 된 경우와 효과가 없는 경우를 모두 공개했다. [임베딩·검색 측정](evaluation/served-embeddings.json) · [기본 해싱 인코더](https://github.com/sokldjs554/five-whys-agent/blob/9dda870837334bc2b0cdc29a30049920028559d8/src/fivewhys/rag/embedder.py) · [벡터·그래프 측정](https://github.com/sokldjs554/five-whys-agent/blob/f8c8e20e848b568b9a1bca9a25168758323b14c2/docs/verification/two-case-retrieval.json) |
| LLM·임베딩 모델 서빙 및 대규모 데이터 처리·최적화 경험 | CPU의 llama.cpp와 별도 ONNX 임베딩 HTTP 프로세스를 실행했다. 실제 임베딩 입력은 보고서 9건·54조각이다. 4,096행 삽입 실험은 합성 벡터의 배치 비용 측정이다. 별도로 KoDoc의 T4 3B 모델 FP16/AWQ, FitWitness의 합성 도면 10만 장 HNSW 비교가 있다. 데이터 규모·하드웨어·측정 대상을 합산하지 않는다. [LLM 실행](local-model.md) · [임베딩·배치 원자료](evaluation/served-embeddings.json) · [T4 측정](https://github.com/sokldjs554/kodoc-ai/blob/d7d332c16e8f3f6eb19d5a9074e0b76e2d7e07c8/benchmarks/results/t4_awq.json) · [10만 장 색인](https://github.com/sokldjs554/fitwitness/blob/197c554412965b22cd69999cb317714bd07abb4b/docs/evaluation/hnsw-recall-real.json) |
| 최신 AI·에이전트 기술을 직접 실험해 본 사이드 프로젝트, 기술 블로그, 오픈소스 기여 등의 경험 | 공개 사이드 프로젝트에 그래프·MCP·로컬 모델의 코드, 입력, 출력, 재현 방법이 있다. 개인 블로그 게시 및 타 프로젝트에 수락된 오픈소스 기여 실적은 이 사례의 근거에 포함하지 않는다. [질문별 실행](evaluation/local-heldout.jsonl) · [비교와 출처](selection.md) |

## 구현·제출·재현 근거

| 자료 | 확인 가능한 범위 |
|---|---|
| 지원자 직접 수행 | QuarterGuard에서 작성자가 제출한 코드·테스트와 그 출처가 남은 범위. 진단 테스트 한 메서드의 하위 사례 둘은 테스트 두 개로 세지 않는다. [제출 파일 해시·실행 주체](https://github.com/sokldjs554/quarterguard/blob/76672afdf76c8b2d2e81819c57523887d26c96a3/artifacts/author-diagnostic-test-20261111/submission.json) |
| 이번 확장의 구현·실행 | 이번 장애 조사 확장의 그래프, 연동, UI, 평가·실행 및 기존 증거 대조. 자기소개서에 해당 코드를 지원자 단독 작성이라고 기재할 근거는 없다. [모델 기록](evaluation/local-heldout.jsonl) · [재확인 항목](selection.md) |
| 지원자 직접 재현 | 이번 확장을 지원자가 로컬에서 실행·판독해 제출한 기록은 아직 없다. 추후 기록에는 리비전·명령·관측한 실패·직접 설명한 원인을 남기면 역할을 확인할 수 있다. |

자료가 보여 주는 것은 합성 장애를 조사하는 개인 프로젝트다. 고객 트래픽 규모, 장기 가용성, 유료 서비스 운영, 학력과 전공은 각각 독립적인 증빙이 필요한 항목이다.
