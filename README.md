# Five Whys Agent

[**공개 데모**](https://sokldjs554.github.io/five-whys-agent/) · [**실제 Claude 조사**](https://sokldjs554.github.io/five-whys-agent/claude.html) · [**백엔드 코드**](https://github.com/sokldjs554/five-whys-agent/tree/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/src/fivewhys/investigation) · [**통합 테스트**](https://github.com/sokldjs554/five-whys-agent/actions/runs/45586350064)

**LLM 에이전트 기반 장애 로그 근본원인분석(RCA) 자동화**

장애가 나면 SRE는 로그를 뒤지고, 배포 이력을 대조하고, "왜?"를 반복하며 근본 원인을
추적합니다. 이 프로젝트는 그 과정 — 도요타의 **5 Whys 기법** — 을 LLM 에이전트의
루프 설계로 옮긴 시스템입니다. 에이전트는 매 단계 도구를 호출해 **로그 증거를 수집**하고,
증거 없는 결론을 내릴 수 없도록 강제됩니다.

```
장애 발생 → [에러 타임라인] → [이상 템플릿 탐지] → [로그 검색/문맥] → [변경 이력 대조]
         → [과거 유사 장애 RAG] → 5 Whys 보고서 (모든 단계에 로그 id 인용)
```

## 공개 데모 · 배포 이후 주문 서비스가 느려진 이유

“배포 이후 주문 서비스의 응답이 느려졌다. 어떤 변경이 관련돼 있나?”를 조사합니다. 공개 데모는 합성 시나리오 `db_pool_exhaustion`을 팀별로 실행해 저장한 기록을 재생합니다. 로그인이나 API 키 없이 열 수 있습니다. 표시되는 작업 ID, 검색 결과, 콜백 이력은 기록 당시의 값입니다.

1. **주문팀 → 조사 기록 열기**를 누릅니다. 첫 원인 후보에서 `order-service v2.4.0` 배포와 로그 인용을 열고, 타임라인에서 변경 시각과 오류 시각을 대조합니다.
2. **벡터 검색과 그래프 검색**에서 후보 순위와 선택·제외 이유를 비교합니다. 그래프 경로를 펼쳐 배포가 변경한 서비스를 확인합니다.
3. **재전송 기록 보기**를 누르면 같은 작업의 콜백이 HTTP 503 이후 200을 받은 이력이 열립니다. 이 규칙 기반 실행의 LLM 호출 수는 재전송 전후 모두 0회입니다.
4. 상단에서 **플랫폼팀**으로 바꿔 같은 사건을 다시 열고 팀별로 조회된 근거를 비교합니다.
5. **실제 Claude 조사 기록 보기**에서 모델이 선택한 세 검색어와 반환 원문을 열고, 가장 유력하다고 본 변경과 확인을 유보한 이유를 읽습니다. [저장된 조사 기록](https://sokldjs554.github.io/five-whys-agent/claude.html)

### 데모 장면에서 코드로

| 확인할 장면 | 구현과 검증 |
|---|---|
| 주문팀·플랫폼팀의 근거 차이 | LangChain 검색기가 Milvus에 팀 필터를 적용하고 Neo4j에서 허용된 서비스 관계를 따라간다. 통합 테스트는 플랫폼 전용 슬로우 쿼리의 ID와 원문 경로를 팀별 검색 결과 및 모델 대역 입력에서 대조한다. [검색 구현](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/src/fivewhys/investigation/retrieval.py) · [후보·경로·원문 접근 테스트](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/tests/test_investigation_flow.py#L94-L127) · [모델 입력 비교](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/tests/test_investigation_flow.py#L278-L286) |
| 콜백 실패 뒤 같은 작업 재전송 | RabbitMQ 워커가 PostgreSQL에 저장한 결과를 재전송한다. 통합 테스트에서 503 → 200 이후 분석은 1회였고 모델 대역 호출은 3회로 유지됐다. [워커](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/src/fivewhys/investigation/worker.py) · [작업 저장](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/src/fivewhys/investigation/jobs.py) · [재전송 전후 비교](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/tests/test_investigation_flow.py#L262-L276) · [DB 실행 횟수 확인](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/tests/test_investigation_flow.py#L288-L302) |

공개 화면은 [Pages 배포본 `a19f7a9`](https://github.com/sokldjs554/five-whys-agent/tree/a19f7a9112789bba7f26a3a56103c7ace48da023)에서 주문팀·플랫폼팀의 기존 Scripted 기록을 재생합니다. 이 기록의 실행 기준은 `4d01473`이고, 해당 실행의 소스와 테스트는 [공개 스냅샷 `2848ab1`](https://github.com/sokldjs554/five-whys-agent/tree/2848ab1e29d44421fdc38f1cbe249d8b65776985)에 있습니다. 플랫폼팀의 실제 Claude 조사는 같은 주문 사건에서 배포와 로그 5건을 인용했습니다. 재전송 전후 분석은 1회, Claude 호출은 2회였습니다. [실행 원자료·판독 기록](https://github.com/sokldjs554/five-whys-agent/tree/7db48acd6a6a2b6e1bb4e34f0c5730a523e456ec/docs/verification/claude/runs/e09c4226-20bf-462f-a673-c5dab75a9f7d) · [실제 호출 실행](https://github.com/sokldjs554/five-whys-agent/actions/runs/45585656133)

확장판을 직접 실행하려면 `demo/incident-backend` 브랜치에서 `docker compose up -d --build --wait` 후 `http://127.0.0.1:8750/`을 엽니다. DB 풀 고갈과 인증서 만료의 검색은 [평가 커밋 `a6cde05`](https://github.com/sokldjs554/five-whys-agent/commit/a6cde056aac7a61c82594e7b9af5551c03cbdd6a)에서 문항별 원문 순위와 지연을 측정했습니다. 기본 브랜치의 CLI·동기 API 실행법은 아래 빠른 시작에 있습니다. [확장판 Compose](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docker-compose.yml) · [두 사건의 측정 결과](https://github.com/sokldjs554/five-whys-agent/blob/b265ee8ee87a0d37720e64bc9451a3dd5aa01d75/docs/verification/TWO_CASE_RETRIEVAL.md) · [검증·인계 보고서](docs/verification/incident-update/README.md)

## 왜 이 프로젝트인가

문서 요약 챗봇류 프로젝트와 달리, 이 프로젝트는 **"LLM의 결론을 어떻게 신뢰할 것인가"**
라는 문제를 정면으로 다룹니다.

1. **증거 강제**: 보고서의 모든 "왜?" 단계는 실제 로그 id를 인용해야 하며,
   평가 하니스가 인용된 id의 실존/시간창 포함 여부를 검증합니다 (환각 인용 탐지).
2. **정량 평가**: 정답을 아는 합성 장애 시나리오 5종(시드 가변)으로
   근본원인 서비스 정확도, 원인 변경 식별율, 증거 정밀도를 자동 채점합니다.
3. **베이스라인 비교**: LLM 없이 동작하는 휴리스틱 엔진(ScriptedLLM)이 같은
   에이전트 루프를 돌기 때문에, "LLM이 휴리스틱 대비 무엇을 더 잘하는가"를
   같은 잣대로 비교할 수 있습니다.

## 핵심 구성 요소

| 구성 요소 | 구현 내용 |
|---|---|
| 로그 템플릿 마이닝 | **Drain 알고리즘 직접 구현** (파라미터 마스킹 + 고정 깊이 prefix tree + 토큰 유사도 병합) |
| 이상 탐지 | 베이스라인 대비 장애 구간 템플릿 발생률 비교 (레벨 가중 log-ratio 스코어) |
| 로그 검색 | SQLite **FTS5 BM25** (운영 규모용 **Elasticsearch 어댑터** 포함, 동일 인터페이스) |
| RAG | 과거 장애보고서 9건 → 섹션 인지 청킹 → 임베딩 → **하이브리드 검색(BM25+벡터+RRF)** |
| 에이전트 | Claude Messages API **수동 tool-use 루프** (7개 도구, 보고서 스키마 pydantic 검증 + 자가 수정) |
| MCP 서버 | 로그 분석 도구를 **MCP 표준**으로 노출 → Claude Desktop/Code에서 바로 사용 |
| 평가 | 규칙 기반 자동 채점 + 선택적 LLM-as-judge (구조화 출력) |
| API/CLI | FastAPI REST API + CLI (`demo` / `evaluate` / `serve` / `mcp-serve`) |

## 아키텍처

```mermaid
flowchart LR
    subgraph 데이터 계층
        S[시나리오 생성기<br/>정답 라벨 포함] --> P[파서]
        P --> D[Drain 템플릿 마이닝]
        D --> DB[(SQLite FTS5<br/>logs · templates · deploys)]
        PM[포스트모템 9건] --> C[섹션 청킹] --> E[해싱 임베딩] --> V[(벡터 스토어)]
        C --> DB
    end

    subgraph 에이전트 루프
        A[Five-Whys Agent] -->|tool_use| T[도구 실행기]
        T --> DB
        T --> V
        T -->|이상 탐지| DB
        A -->|submit_report| R[RCA 보고서<br/>pydantic 검증]
    end

    subgraph 엔진
        CL[Claude API] -.LLMClient.-> A
        SC[ScriptedLLM<br/>오프라인 베이스라인] -.LLMClient.-> A
    end

    R --> EV[평가 하니스<br/>정확도 · 증거 정밀도]
```

## 빠른 시작

```bash
git clone https://github.com/sokldjs554/five-whys-agent.git && cd five-whys-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,mcp]"

# 1) API 키 없이 바로 실행되는 오프라인 데모 (휴리스틱 베이스라인)
fivewhys demo --scenario db_pool_exhaustion

# 2) Claude 에이전트로 실행
export ANTHROPIC_API_KEY=sk-ant-...
fivewhys demo --scenario cache_stampede --engine claude

# 3) 전 시나리오 정량 평가
fivewhys evaluate --engine scripted --runs 3

# 4) REST API
fivewhys serve   # POST /analyze, GET /scenarios, GET /reports/{id}

# 5) MCP 서버 (Claude Desktop/Code 연동)
fivewhys mcp-serve --scenario db_pool_exhaustion

# 테스트
pytest
```

### 선택 실습

```bash
# MCP 서버 — 호스트 앱 없이 MCP 인터페이스(list_tools/call_tool)를 직접 호출
python examples/mcp_client_demo.py

# Elasticsearch 백엔드 — 같은 질의를 SQLite/ES 두 저장소에 던져 비교
docker compose up -d && pip install -e ".[es]"
python examples/es_backend_demo.py

# LLM-as-judge — 규칙 채점 + 인과 사슬 일관성 LLM 판정 (API 키 필요)
python examples/judge_demo.py
```

## 데모 출력 (오프라인, API 키 불필요)

```
[5 Whys 인과 사슬]
  Why 1. 왜 사용자 요청에 문제가 생겼는가?
     → api-gateway에서 'Upstream timeout: order-service GET <*> ...' 패턴이
       급증했다 (장애 구간 48건, 베이스라인 0건).   증거 로그: [1913, 1916, 1925]
  Why 2. 왜 api-gateway의 처리에 문제가 생겼는가?
     → order-service에서 'HikariPool-1 - Connection is not available ...' 패턴이
       급증했다 (장애 구간 58건, 베이스라인 0건).   증거 로그: [1819, 1821, 1823]
  Why 3. 왜 order-service에서 이 문제가 시작됐는가?
     → 장애 직전 변경: order-service v2.4.0 배포 — 주문 조회 쿼리 리팩터링

[근본 원인] (order-service) ... 트리거는 'v2.4.0 배포'로 판단
[유사 과거 장애] 2025-11-14-db-connection-pool
```

## 평가 결과

**베이스라인** — 시나리오 5종 × 시드 3개 = 15회 (`fivewhys evaluate --runs 3`):

| 엔진 | 근본원인 서비스 정확도 | 키워드 정확도 | 원인 변경 식별 | 평균 증거 정밀도 |
|---|---|---|---|---|
| scripted (휴리스틱) | 100% (15/15) | 100% | 100% | 1.00 |

**LLM 엔진 대비** — 동일 시나리오를 Claude 에이전트로 실행한 결과:

| 지표 | scripted | Claude (claude-opus-5) |
|---|---|---|
| 근본원인 서비스 / 원인 변경 식별 | 정확 | 정확 |
| 증거 정밀도 (환각 인용 없음) | 1.00 | **1.00** |
| 인용한 로그 수 | 6~12건 | **24~30건** |
| 왜? 체인 깊이 | 3~5단계 | **5~6단계** |
| 재발 방지 대책 수 | 3건 (규칙 기반 템플릿) | **7건 (맥락 기반)** |

**정확도는 같지만 분석의 깊이가 다릅니다.** 두 엔진 모두 근본 원인 서비스와 원인 배포를
맞히지만, LLM 에이전트는 인과 사슬을 조직적 원인까지 밀고 내려갑니다:

> *"…근본적으로는 배포 전 EXPLAIN 검토·슬로우쿼리 회귀 게이트가 CI에 없어 인덱스
> 미보유 쿼리가 걸러지지 않았고, 2025-11-14 동일 장애의 대책(인덱스 추가·CI 게이트)이
> 실질적으로 유지·완료되지 않아 그대로 재발했다."*
>
> — Claude 엔진, `db_pool_exhaustion` (Why 5)

과거 포스트모템(RAG로 검색한 문서)에 "[완료] 인덱스 추가"로 기록돼 있는데도 같은 장애가
재발했다는 **모순을 스스로 발견**하고, 스키마 드리프트 검사와 액션 아이템 이행 감사를
대책으로 제안했습니다. 이는 설계에 넣은 규칙이 아니라 증거 수집 과정에서 도출된 것으로,
휴리스틱 베이스라인이 원리적으로 도달할 수 없는 지점입니다.

측정 항목:
- **근본원인 서비스 정확도** — 인과 사슬의 출발 서비스를 맞췄는가 (에러가 가장 많은 서비스 ≠ 근본 원인)
- **원인 변경 식별** — 장애를 유발한 배포/설정 변경을 특정했는가
- **증거 정밀도** — 인용한 로그 id가 실존하며 장애 구간에 속하는 비율 (환각 인용 탐지)

> 합성 시나리오의 난이도상 베이스라인도 정확도 만점을 받습니다. 정확도 격차를 만들려면
> 휴리스틱이 원리적으로 실패하는 시나리오가 필요하며, 그 설계는
> [docs/EVALUATION.md](docs/EVALUATION.md)의 로드맵에 정리했습니다.

## 기술적 의사결정

| 결정 | 이유 |
|---|---|
| Drain을 라이브러리 대신 직접 구현 | 대용량 로그 → 템플릿 압축이 이 도메인의 핵심이라 내부 동작을 이해하고 통제해야 했음. 테스트에 알고리즘의 알려진 한계(선행 토큰 파라미터 분화)도 명시 |
| SQLite FTS5 기본 + ES 어댑터 | 로컬에서 외부 의존성 0으로 전체 파이프라인 실행 가능. 검색 인터페이스를 추상화해 운영 환경에서는 Elasticsearch로 교체 (`store/es.py` + docker-compose) |
| RRF 하이브리드 검색 | BM25(정확 용어)와 벡터(의미 유사) 랭킹을 점수 보정 없이 순위로 융합 — Elasticsearch hybrid search와 동일 방식 |
| 수동 tool-use 루프 | SDK 헬퍼 대신 루프를 직접 구현해 (1) LLMClient 추상화로 오프라인 엔진 교체 가능 (2) 보고서 제출을 가로채 pydantic 검증 → 실패 시 오류를 돌려줘 모델이 자가 수정 |
| ScriptedLLM 베이스라인 | "에이전트 루프"와 "LLM 품질"을 분리해 테스트. CI에서 API 비용 0으로 전체 통합 테스트, 평가에서는 LLM 대비 기준선 역할 |
| 임베딩 추상화 (기본: 해싱 벡터라이저) | 외부 모델 의존 없이 결정적으로 동작 → 재현 가능한 테스트. `Embedder` 프로토콜만 만족하면 sentence-transformers 등으로 교체 가능 |
| 합성 시나리오 + 정답 라벨 | LLM 출력의 "그럴듯함"이 아니라 검증 가능한 정확도로 평가. 실로그는 정답이 없어 정량 평가 불가 |

## 프로젝트 구조

```
src/fivewhys/
├── logs/          # parser, drain(템플릿 마이닝), anomaly(이상 탐지)
├── store/         # SQLite FTS5 저장소, Elasticsearch 어댑터
├── rag/           # chunker, embedder, vectorstore, retriever(RRF)
├── scenarios/     # 정답 라벨 포함 합성 장애 시나리오 5종
├── agent/         # LLM 추상화, 도구 정의/실행기, Five-Whys 루프, 오프라인 엔진
├── evaluation/    # 규칙 기반 채점 하니스, LLM-as-judge
├── mcp_server/    # MCP 표준 서버 (Claude Desktop/Code 연동)
├── data/postmortems/  # 과거 장애 보고서 코퍼스 9건 (RAG 지식베이스)
├── api.py         # FastAPI REST API
└── cli.py         # CLI 진입점
tests/             # 69개 테스트 (전부 오프라인, API 키 불필요)
```

## 한계와 로드맵

- **합성 데이터의 한계**: 시나리오가 "변경 → 장애" 패턴에 치우쳐 있어 베이스라인도
  만점이 나온다. 실제 가치 검증을 위해 휴리스틱이 실패하는 시나리오
  (다중 복합 원인, 로그에 없는 원인, 오해를 유발하는 무관 배포)를 추가할 계획
- **스트리밍 적재**: 현재는 배치 적재. Drain은 온라인 알고리즘이므로 Kafka 등
  스트림 소스 연결이 자연스러운 다음 단계
- **임베딩 업그레이드**: 해싱 벡터라이저 → 다국어 임베딩 모델 교체 후 검색 품질 A/B
- **LLM-judge 상시화**: 현재는 선택 실행. 체인 일관성 채점을 평가 기본 항목으로 편입

## 라이선스

MIT
