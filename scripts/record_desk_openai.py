"""Record two one-call investigations using fixed development questions."""
import asyncio
import os
import sys
from pathlib import Path

from desk_eval import DATA, read, score, validate_freeze, write
from fivewhys.desk.engine import investigate
from fivewhys.desk.openai_planner import OpenAIPlanner


async def main(out):
    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise SystemExit("Missing GitHub Actions secret OPENAI_API_KEY")
    validate_freeze()
    cases = read(DATA / "development.json")
    result = {"commit":os.getenv("GITHUB_SHA"), "actions_run_id":os.getenv("GITHUB_RUN_ID"), "runs":[]}
    for case_id in ("dev-01", "dev-02"):
        case = next(c for c in cases if c["id"] == case_id)
        planner = OpenAIPlanner()
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


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
