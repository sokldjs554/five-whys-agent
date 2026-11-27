# CPU에서 실제 조사 계획 재현하기

Qwen2.5-1.5B-Instruct가 질문과 MCP에서 발견한 도구 이름·설명을 읽고, 먼저 실행할 도구와 로그·과거 문서 검색어를 JSON으로 생성한다. 조사 정책은 세 출처를 모두 확인하며 로그는 최대 5개, 과거 문서 조각은 최대 4개를 요청한다. LangGraph는 모델이 고른 도구부터 호출하고 각 MCP 결과를 검증한다. 최종 답변과 인용은 검증한 증거로 프로그램이 작성한다. [계획 어댑터](../../src/fivewhys/desk/local_model.py) · [그래프](../../src/fivewhys/desk/engine.py)

## 실행 환경

| 항목 | 고정한 값 |
| --- | --- |
| 모델 | Qwen2.5-1.5B-Instruct-GGUF, Q4_K_M, Apache-2.0 |
| 가중치 | 1,117,320,736바이트, 리비전 `91cad51170dc346986eccefdc2dd33a9da36ead9` |
| 가중치 SHA-256 | `6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e` |
| 추론 서버 | llama.cpp `b7757` (`c945aaaef`), MIT, Ubuntu x86-64 CPU 바이너리 |
| 측정 환경 | Linux x86-64, AMD EPYC 9V74, 서버 스레드 3개, 동시 추론 슬롯 1개 |
| 생성 설정 | 컨텍스트 2,048토큰, 최대 출력 160토큰, 온도 0, 시드 42, JSON Schema 제약 |

[공식 모델·라이선스](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/tree/91cad51170dc346986eccefdc2dd33a9da36ead9) · [추론 서버 릴리스](https://github.com/ggml-org/llama.cpp/releases/tag/b7757) · [추론 서버 라이선스](https://github.com/ggml-org/llama.cpp/blob/b7757/LICENSE)

Linux x86-64에서 프로젝트의 Python 환경을 활성화한 뒤 아래 명령을 실행한다. 스크립트가 캐시에 가중치와 바이너리를 내려받고 두 파일의 해시를 확인한다. 터미널을 열어 두면 루프백의 18081 포트에서 CPU 서버가 실행된다.

```bash
bash scripts/serve_desk_model.sh
```

같은 Python 환경의 다른 터미널에서 다음 명령으로 MCP 도구 목록을 읽고 새 모델 응답 세 건을 얻는다. 마지막 검사에서는 사용하지 않는 로컬 포트에 접속해 장애를 재현한다. `FIVEWHYS_MODEL_CACHE`로 다운로드 위치를, `FIVEWHYS_MODEL_PORT`로 서버 포트를 바꿀 수 있다. 포트를 바꿨다면 클라이언트의 `FIVEWHYS_LOCAL_MODEL_URL`에도 `/v1/chat/completions`를 포함한 전체 URL을 지정한다.

```bash
curl --fail http://127.0.0.1:18081/health
FIVEWHYS_PLANNER_VERSION=v1 python scripts/probe_desk_model.py
```

## 최초 버전의 도구 순서 선택

| 질문 요지 | 모델이 고른 첫 도구 | 입력 / 출력 토큰 | 요청 시간 |
| --- | --- | ---: | ---: |
| HikariPool 관련 과거 보고서 먼저 확인 | `search_past_incidents` | 295 / 44 | 4.14초 |
| 같은 질문을 새 요청으로 재실행 | `search_past_incidents` | 295 / 44 | 4.49초 |
| 배포 변경 먼저 확인 | `list_change_events` | 293 / 38 | 6.22초 |

세 응답의 서버 요청 ID는 각각 다르다. 마지막 질문에서 모델이 선택한 로그 검색어 `deployment change`는 로그 원문에서 찾기 어려운 일반 표현이다. 최종 인용 품질은 별도의 그래프 평가에서 검사한다. 로컬 연결 거부를 유도한 경우 1.8ms 뒤 `LocalModelError`가 발생했고 도구 실행 계획은 생성되지 않았다. 요청 시간에는 서버 대기와 추론이 포함됐다. [질문·계획·사용량 원본](evaluation/local-planner-probe.json) · [재현 스크립트](../../scripts/probe_desk_model.py)

## 개발 질문으로 개선한 검색어 선택

최초 버전(v1)은 자유롭게 검색어를 생성했다. 한국어 개발 질문에서 `order failure cause`와 `past incident`를 골랐을 때, 로그 상위 결과는 평상시 주문 조회였다. 같은 질문의 세 실행에서 모두 검증을 통과하지 못했다. 당시 사용한 어댑터 설정은 `FIVEWHYS_PLANNER_VERSION=v1`로 다시 선택할 수 있다. [최초 개발 실행](evaluation/initial/local-development.jsonl)

현재 기본 버전(v2)은 저장소에 포함된 과거 보고서 9건의 제목과 요약에서 영문 기술 용어를 추출한다. 여러 요약에 똑같이 등장하는 용어를 제외하고, 질문과 각 제목·용어의 겹침을 전체 문서 빈도의 역수로 가중한다. 최고 점수의 65% 이상인 상위 두 보고서까지 후보로 삼아 모델이 검색어를 고르게 한다. 어휘가 겹치지 않으면 모델이 자유롭게 검색어를 작성한다. 두 경로 모두 질문마다 모델 요청은 한 번이다. 용어 선택에 쓴 과거 문서는 현재 시점의 로그와 변경 이력을 검증하는 단계에 별도 증거로 전달되지 않는다. [어휘 추출·매칭](../../src/fivewhys/desk/vocabulary.py) · [계획 검증](../../src/fivewhys/desk/local_model.py)

개발 과정에서 한국어·영어 양성 질문 두 개를 확인했다. 모든 보고서의 용어를 한꺼번에 제시한 실험에서는 한국어 질문의 계획이 실패했고, 영어 질문에는 관련 없는 검색어가 섞였다. 영문 단어를 정확히 매칭하고 문서 전체에서 흔한 용어의 가중치를 줄인 뒤 두 질문에서 모두 검증 가능한 로그·배포·과거 보고서가 검색됐다. 아래 명령은 개발 질문에 대해 세 차례 전체 그래프를 실행한다. 기존 측정치를 보존하려면 출력 디렉터리를 별도로 지정한다.

```bash
FIVEWHYS_PLANNER_VERSION=v2 python scripts/desk_eval.py \
  --mode local --split development --repeats 3 --results-dir /tmp/fivewhys-v2-development
```

6개 개발 질문을 각 3회 실행한 결과, 근거를 갖춰 답한 양성 사례는 v1의 3/6에서 v2의 6/6으로 증가했다. 보류해야 할 사례는 두 버전 모두 12/12에서 올바르게 보류했다. 전체 성공은 15/18에서 18/18로 변했다. v2는 고유한 Qwen 응답 12건에서 입력 3,828토큰, 출력 425토큰을 기록했다. 나머지 실행은 범위 검사 또는 오류 주입용 계획을 사용했다. 이 수치는 개발에 사용한 질문에서 측정했다. [v1 요약](evaluation/initial/local-development-summary.json) · [v2 요약](evaluation/v2/local-development-summary.json) · [v2 실행 원문](evaluation/v2/local-development.jsonl)
