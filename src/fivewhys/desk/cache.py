"""Optional short-lived cache for immutable, successful desk reports."""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis import Redis

log = logging.getLogger(__name__)


class ResultCache:
    def __init__(self, client: Redis | None = None, *, namespace: str = "fivewhys:desk:v1", ttl: int = 300):
        self.client = client
        self.namespace = namespace
        self.ttl = ttl

    def get(self, job_id: str) -> dict | None:
        if self.client is None:
            return None
        from redis.exceptions import RedisError

        try:
            raw = self.client.get(f"{self.namespace}:result:{job_id}")
            if raw is None:
                return None
            value = json.loads(raw)
            if (
                isinstance(value, dict)
                and value.get("id") == job_id
                and value.get("status") in ("answered", "withheld")
                and isinstance(value.get("question"), str)
                and isinstance(value.get("answer"), str)
                and isinstance(value.get("steps"), list)
                and isinstance(value.get("citations"), list)
            ):
                return value
            return None
        except (RedisError, ValueError, UnicodeError):
            log.warning("Desk result cache read failed")
            return None

    def put(self, job_id: str, result: dict) -> None:
        if self.client is None:
            return
        from redis.exceptions import RedisError

        try:
            self.client.set(
                f"{self.namespace}:result:{job_id}",
                json.dumps(result, ensure_ascii=False),
                ex=self.ttl,
            )
        except RedisError:
            log.warning("Desk result cache write failed")


def make_cache_from_env() -> ResultCache:
    url = os.environ.get("DESK_REDIS_URL")
    if not url:
        return ResultCache()

    try:
        from redis import Redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        ttl = int(os.environ.get("DESK_CACHE_TTL", "300"))
        if ttl <= 0:
            raise ValueError("TTL must be positive")
        client = Redis.from_url(
            url, socket_connect_timeout=0.2, socket_timeout=0.2,
            retry=Retry(NoBackoff(), 0), decode_responses=False,
        )
    except (ImportError, ValueError):
        log.warning("Desk result cache disabled due to configuration or missing redis-py")
        return ResultCache()

    return ResultCache(
        client, namespace=os.environ.get("DESK_CACHE_NAMESPACE", "fivewhys:desk:v1"), ttl=ttl,
    )
