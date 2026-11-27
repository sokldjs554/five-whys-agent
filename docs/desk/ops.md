# Kubernetes에서 조사 결과 복구 확인

한 노드의 로컬 K3s에 API와 Redis를 각각 한 개의 Pod로 배포했다. API Service로 주문 서비스의 DB 연결 풀 오류와 관련된 배포를 물었고, 작업은 `queued → running → completed`로 진행됐다. 규칙 엔진이 실제 MCP stdio 도구 세 개를 호출해 인용 세 개가 있는 답을 반환했다. 이 클러스터에서 해당 조사에 사용한 모델 호출 수는 0이다. [실행 기록](ops-evidence.json) · [별도 CPU 모델 서빙 실험](local-model.md)

| 확인 항목 | 관찰한 결과 |
| --- | --- |
| 배포 상태 | K3s v1.32.8+k3s1에서 API·Redis가 각각 1/1 Ready. SQLite를 저장한 128Mi RWO PVC가 Bound 상태 |
| 첫 조회와 반복 조회 | 독립된 Redis 7.4.12에서 첫 결과 조회 시 miss 1회, 두 번째 결과 조회 시 hit 1회. 해당 키에 남은 TTL 286초 |
| Redis 중단과 API 교체 | Redis를 0개로 줄이고 Pod 삭제를 확인한 뒤 API를 다시 배포. 새 API Pod에서 기존 작업을 다시 조회했고 두 응답의 SHA-256이 교체 전과 일치 |
| Redis 재생성 | 빈 Redis Pod를 다시 띄운 뒤 결과를 두 번 조회. 같은 응답을 돌려받았고 새 인스턴스에 miss와 hit가 한 번씩 누적 |

API는 SQLite에서 작업 존재 여부와 최종 상태를 먼저 읽는다. Redis에는 `DESK_CACHE_NAMESPACE:result:<job_id>`에 완성된 보고서만 최대 `DESK_CACHE_TTL`초 저장한다. 기본값은 300초다. 캐시 연결과 명령의 타임아웃은 각각 0.2초이며 재시도 횟수는 0이다. 캐시 값의 ID·상태·필드 형식 검사에 실패하거나 Redis가 응답하지 않으면 SQLite에서 결과를 읽는다. `DESK_REDIS_URL`을 생략하면 SQLite만 사용한다. [캐시 구현](../../src/fivewhys/desk/cache.py) · [실제 Redis 왕복·TTL 테스트](../../tests/test_desk_cache.py)

## 로컬에서 재현

Docker, kind, kubectl, Python 3을 준비하고 저장소 루트에서 실행한다. PostgreSQL이나 모델 API 키는 필요하지 않다. 매니페스트는 기본 StorageClass가 있는 로컬 클러스터용이다. 같은 PVC를 두 프로세스가 교체 중에 동시에 사용하지 않도록 API 복제본·Uvicorn 워커는 한 개로 고정하고 Recreate로 교체한다.

```sh
kind create cluster --name fivewhys-desk
docker build -f deploy/desk/Dockerfile -t fivewhys-desk:local .
kind load docker-image fivewhys-desk:local --name fivewhys-desk
kubectl --context kind-fivewhys-desk apply -f deploy/desk/kubernetes.yaml
kubectl --context kind-fivewhys-desk -n fivewhys-desk rollout status deploy/redis
kubectl --context kind-fivewhys-desk -n fivewhys-desk rollout status deploy/desk
kubectl --context kind-fivewhys-desk -n fivewhys-desk port-forward svc/desk 8000:8000
```

다른 터미널에서 아래 명령을 실행한다. 스크립트가 HTTP로 새 작업을 접수하고 완료 상태까지 조회한 뒤 동일 결과를 두 번 읽어 ID와 해시를 출력한다. 브라우저의 `http://127.0.0.1:8000/desk/`에서도 조사할 수 있다.

```sh
python deploy/desk/smoke.py http://127.0.0.1:8000
```

같은 작업으로 복구를 검증하려면 위에서 출력된 ID를 `JOB_ID`에 넣는다. Redis를 내린 뒤 API를 교체하면 기존 포트 포워딩이 종료될 수 있다. 앞의 포트 포워딩 명령을 새로 실행하고 다음 결과의 해시를 처음 값과 비교한다.

```sh
kubectl --context kind-fivewhys-desk -n fivewhys-desk scale deploy/redis --replicas=0
kubectl --context kind-fivewhys-desk -n fivewhys-desk wait --for=delete pod -l app=desk-cache --timeout=60s
kubectl --context kind-fivewhys-desk -n fivewhys-desk rollout restart deploy/desk
kubectl --context kind-fivewhys-desk -n fivewhys-desk rollout status deploy/desk
# 다른 터미널에서 포트 포워딩을 다시 시작한다.
python deploy/desk/smoke.py --existing "$JOB_ID"
kubectl --context kind-fivewhys-desk -n fivewhys-desk scale deploy/redis --replicas=1
```

재현이 끝나면 `kind delete cluster --name fivewhys-desk`로 실습 클러스터와 그 안의 데이터를 삭제한다.

## 측정 환경과 범위

기록한 실행에서는 rootless Docker 29.9.2 안에서 K3s를 띄우고 외부 포트를 게시하지 않은 API ClusterIP로 HTTP 요청을 보냈다. 이 호스트에는 하위 cgroup 위임이 없어 Kubelet의 사용자 네임스페이스 옵션과 crun 1.23.1의 cgroup 비활성 옵션을 사용했다. 컨테이너별 메모리 제한 강제, 다중 노드 장애 전환, 동시 고부하 처리량은 측정 범위 밖이다. Redis 데이터는 휘발성이며, SQLite 복구 범위는 같은 PVC를 다시 마운트한 API Pod 교체까지다.
