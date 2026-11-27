"""Measure the optional encoder through the same retriever and MCP client as the API."""
import argparse
import asyncio
import importlib.metadata as md
import json
import os
import platform
import time

import numpy as np

from fivewhys.desk.engine import investigate
from fivewhys.desk.local_model import LocalPlanner
from fivewhys.pipeline import DEFAULT_POSTMORTEM_DIR
from fivewhys.rag.chunker import chunk_markdown
from fivewhys.rag.vectorstore import VectorStore


def insertion_runs():
    vectors = np.random.default_rng(42).normal(size=(4096, 384)).astype("float32")
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    rows = []
    for batch_size in [1, 32]:
        for repeat in range(3):
            store = VectorStore(384)
            t0 = time.perf_counter()
            for start in range(0, len(vectors), batch_size):
                end = start + batch_size
                store.add_batch(list(range(start,end)), vectors[start:end])
            elapsed = time.perf_counter() - t0
            rows.append(dict(batch_size=batch_size, repeat=repeat+1, elapsed_ms=1000*elapsed,
                             top5=[i for i,_ in store.search(vectors[0],5)]))
    if any(row["top5"] != rows[0]["top5"] for row in rows):
        raise ValueError("Insertion changed ranking")
    return rows


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not os.getenv("DESK_EMBEDDING_URL"):
        parser.error("Set DESK_EMBEDDING_URL to the running encoder endpoint")
    docs = sorted(DEFAULT_POSTMORTEM_DIR.glob("*.md"))
    record = dict(platform=platform.platform(), python=platform.python_version(),
                  cpu_quota=open("/sys/fs/cgroup/cpu.max").read().strip()
                  if os.path.isfile("/sys/fs/cgroup/cpu.max") else None,
                  versions={pkg:md.version(pkg) for pkg in
                            ["onnxruntime","tokenizers","numpy","langgraph","mcp"]},
                  encoder_revision="e8f8c211226b894fcb81acc59f3b34ba3efd5f42",
                  documents=len(docs), chunks=sum(len(chunk_markdown(p.stem,p.read_text())) for p in docs),
                  dimension=384, insertion_rows=4096, insertion_runs=insertion_runs(), investigations=[])
    for name, planner in [("rules", None), ("qwen", LocalPlanner.from_env())]:
        for question in ["주문 서비스의 DB 연결 풀 오류와 관련된 배포를 조사해 줘",
                         "Which deployment preceded the order-service HikariPool timeout?"]:
            t0 = time.perf_counter()
            result = await investigate(question, planner=planner, timeout_seconds=60)
            record["investigations"].append(dict(planner=name, elapsed_ms=(time.perf_counter()-t0)*1000,
                                                 record=result))
    with open(args.output, "w") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
