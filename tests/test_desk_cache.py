import json
import os
import uuid

import pytest

from fivewhys.desk.cache import make_cache_from_env


def test_cache_disabled_without_url(monkeypatch):
    monkeypatch.delenv("DESK_REDIS_URL", raising=False)
    cache = make_cache_from_env()
    cache.put("id", {"answer": "완료"})
    assert cache.get("id") is None


def test_unavailable_redis_falls_back(monkeypatch):
    pytest.importorskip("redis")
    monkeypatch.setenv("DESK_REDIS_URL", "redis://127.0.0.1:1/0")
    cache = make_cache_from_env()
    assert cache.client is not None
    assert cache.get("id") is None
    cache.put("id", {"answer": "완료"})


@pytest.mark.skipif(not os.environ.get("DESK_TEST_REDIS_URL"), reason="requires disposable Redis")
def test_real_redis_round_trip_ttl_and_corrupt_payload(monkeypatch):
    pytest.importorskip("redis")
    namespace = f"fivewhys:test:{uuid.uuid4()}"
    monkeypatch.setenv("DESK_REDIS_URL", os.environ["DESK_TEST_REDIS_URL"])
    monkeypatch.setenv("DESK_CACHE_NAMESPACE", namespace)
    monkeypatch.setenv("DESK_CACHE_TTL", "30")
    cache = make_cache_from_env()
    key = f"{namespace}:result:sample"
    try:
        assert cache.get("sample") is None
        expected = {"id": "sample", "status": "answered", "question": "DB 오류?",
                    "answer": "배포를 확인하세요", "steps": [], "citations": ["D-01"]}
        cache.put("sample", expected)
        assert cache.get("sample") == expected
        assert 0 < cache.client.ttl(key) <= 30
        cache.client.set(key, "broken-json", ex=30)
        assert cache.get("sample") is None
        for payload in ([], {}, {**expected, "id": "other"}, {**expected, "status": "running"}):
            cache.client.set(key, json.dumps(payload), ex=30)
            assert cache.get("sample") is None
    finally:
        cache.client.delete(key)
        cache.client.close()
