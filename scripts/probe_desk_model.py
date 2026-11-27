"""Run three independent planner requests and a real connection-refused control."""

import argparse
import asyncio
import json
from pathlib import Path
import socket
from time import monotonic

from fivewhys.desk.local_model import LocalModelError, LocalPlanner
from fivewhys.desk.mcp_tools import desk_session, discover, validate_plan

QUESTIONS = [
    "Which previous postmortem describes HikariPool connection exhaustion? Start with prior reports.",
    "Which deployment changed first? Check changes before looking for HikariPool timeouts.",
]


async def probe():
    async with desk_session() as session:
        tools = await discover(session)
    planner = LocalPlanner.from_env()
    runs = []
    for question in (QUESTIONS[0], QUESTIONS[0], QUESTIONS[1]):
        calls = validate_plan(await planner(question, tools))
        runs.append({"question": question, "calls": calls, "usage": planner.last_usage})
    if len({r["usage"]["request_id"] for r in runs}) != len(runs):
        raise RuntimeError("Expected an independent completion ID per invocation")
    with socket.socket() as unavailable:
        # Hold an unused loopback port without listening; do not interrupt a running service.
        unavailable.bind(("127.0.0.1", 0))
        port = unavailable.getsockname()[1]
        offline = LocalPlanner(url=f"http://127.0.0.1:{port}/v1/chat/completions")
        started = monotonic()
        try:
            await offline(QUESTIONS[0], tools)
        except LocalModelError as exc:
            failure = {
                "condition": "connection_refused",
                "error": str(exc),
                "elapsed_ms": round(1000 * (monotonic() - started), 1),
                "provider_usage": offline.last_usage,
            }
        else:
            raise RuntimeError("Expected unavailable planner to fail closed")
    return {
        "scope": "planner only, real MCP discovery and model inference",
        "model_revision": "91cad51170dc346986eccefdc2dd33a9da36ead9",
        "llama_cpp_build": "b7757",
        "quantization": "Q4_K_M",
        "runs": runs,
        "failure_control": failure,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.dumps(asyncio.run(probe()), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
