# 한국어 문서 임베딩 서빙과 색인 배치 측정

기본 실행은 512차원 문자·단어 해싱, SQLite FTS5와 RRF를 사용한다. 이번 별도 실험은 같은 검색 API에서 다국어 MiniLM으로 인코더를 교체했다. 문서 9개를 섹션 기준 54개로 분할하고 최대 32개씩 HTTP로 보내 384차원 벡터를 받는다. 질의에도 같은 인코더를 쓴다. MCP 자식 프로세스에는 인코더 주소만 추가로 전달한다. 수신 측은 개수·차원·유한값·단위 노름을 검사한다.

Sentence Transformers가 배포한 Apache-2.0 모델의 고정 리비전에서 x86 AVX2 양자화 ONNX 파일과 토크나이저를 받는다. ONNX Runtime CPU에서 attention mask 평균 풀링과 L2 정규화를 적용했다. 스크립트가 두 파일의 SHA-256을 확인한다. [모델 및 라이선스](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2/tree/e8f8c211226b894fcb81acc59f3b34ba3efd5f42)

가상환경을 활성화한 저장소 루트에서 실행한다.

```sh
python -m pip install -e '.[dev,desk-encoder]'
bash scripts/serve_desk_embeddings.sh
# 두 번째 터미널에서, 같은 가상환경 사용
export DESK_EMBEDDING_URL=http://127.0.0.1:18082/embeddings
python -m uvicorn fivewhys.api:app
# Qwen 서버도 실행한 상태에서만 4개 전체 조사 측정 가능
python scripts/measure_desk_embeddings.py --output /tmp/served-embeddings.json
```

규칙 계획과 Qwen 계획 각각에 한국어·영어 질문 1개씩을 넣었다. 원자료에는 모델 호출, 도구별 실제 결과, 인용, 소요 시간이 있다. 이 실험의 표본은 4회이며 검색 품질 비교를 위한 독립 평가셋은 별도 문서를 따른다. [실행 원자료](evaluation/served-embeddings.json)

벡터를 하나씩 추가하면 NumPy 배열을 매번 복사한다. 같은 4,096개 합성 벡터를 하나씩 혹은 32개씩 입력하고 같은 질의의 상위 5개 ID가 일치하는지 확인했다. 각 조건 3회 시간은 원자료의 `insertion_runs`에 있다. 측정 구간은 인메모리 벡터 추가 루프다. 모델 추론, SQLite 쓰기, 검색 지연, 운영 트래픽은 이 구간에서 제외했다. 4 vCPU 할당의 공유 환경에서 측정했다. 대규모 운영 경험은 이 자료로 확인할 수 없다.
