"""ES 어댑터: 실제 클러스터 없이 질의 변환과 응답 매핑을 검증한다."""

from datetime import datetime

from fivewhys.models import KST
from fivewhys.store.es import ElasticsearchLogSearch


class StubES:
    def __init__(self):
        self.last_query = None

    def search(self, index, query, size):
        self.last_query = {"index": index, "query": query, "size": size}
        return {
            "hits": {
                "hits": [
                    {
                        "_id": "17",
                        "_score": 3.2,
                        "_source": {
                            "ts": "2026-07-03T14:05:00+09:00",
                            "service": "order-service",
                            "level": "ERROR",
                            "component": "db-pool",
                            "message": "Connection is not available",
                            "template_id": 4,
                        },
                    }
                ]
            }
        }


def test_build_query_structure():
    es = ElasticsearchLogSearch(client=StubES())
    q = es.build_query(
        "connection pool",
        service="order-service",
        level="ERROR",
        start=datetime(2026, 7, 3, 14, 0, tzinfo=KST),
    )
    assert q["bool"]["must"][0]["match"]["message"]["query"] == "connection pool"
    filters = q["bool"]["filter"]
    assert {"term": {"service": "order-service"}} in filters
    assert {"term": {"level": "ERROR"}} in filters
    assert any("range" in f for f in filters)


def test_search_logs_maps_hits():
    stub = StubES()
    es = ElasticsearchLogSearch(client=stub, index="test-idx")
    rows = es.search_logs("connection", limit=5)
    assert stub.last_query["index"] == "test-idx"
    assert stub.last_query["size"] == 5
    assert rows[0]["id"] == 17
    assert rows[0]["service"] == "order-service"
    assert rows[0]["message"] == "Connection is not available"
