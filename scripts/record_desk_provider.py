"""Record two one-call investigations using fixed development questions."""
import asyncio
import os
import sys
from pathlib import Path

from desk_eval import DATA, read, score, validate_freeze, write
from fivewhys.desk.engine import investigate
from fivewhys.desk.openai_planner import OpenAIPlanner


async def record(out, provider, create_planner):
    validate_freeze()
    cases = read(DATA / "development.json")
    result = {"provider":provider, "commit":os.getenv("GITHUB_SHA"), "actions_run_id":os.getenv("GITHUB_RUN_ID"), "runs":[]}
    for case_id in ("dev-01", "dev-02"):
        case = next(c for c in cases if c["id"] == case_id)
        planner = create_planner()
        run = await investigate(case["question"], planner=planner, timeout_seconds=55)
        graded = score(case, run)
        result["runs"].append({"case":case_id, "provider_http":planner.provider_status,
                               "provider_error":planner.error_code, "trace":run, "score":graded})
        write(out, result)
        print(case_id, "HTTP", planner.provider_status, planner.error_code,
              run["status"], run["reason"], "MCP calls", len(run["steps"]), flush=True)
        if planner.provider_status != 200:
            raise SystemExit("Provider request did not succeed. See sanitized status above.")
    if any(not item["trace"].get("model_usage") for item in result["runs"]):
        raise SystemExit("Missing completed provider response")


async def main(out, provider):
    if provider == "openai":
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise SystemExit("Missing GitHub Actions secret OPENAI_API_KEY")
        return await record(out, provider, OpenAIPlanner)
    if provider != "claude":
        raise ValueError("Unknown provider")
    import anthropic
    from fivewhys.desk.claude_planner import ClaudePlanner, available_model

    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise SystemExit("Missing GitHub Actions secret ANTHROPIC_API_KEY")
    async with anthropic.AsyncAnthropic(api_key=key, max_retries=0, timeout=30) as client:
        try:
            model = await available_model(client)
        except anthropic.APIStatusError as exc:
            raise SystemExit(f"Model discovery rejected: HTTP {exc.status_code}") from None
        await record(out, provider, lambda: ClaudePlanner(client, model))


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[2]), sys.argv[1]))
