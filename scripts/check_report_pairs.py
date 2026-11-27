"""Run every pair of bundled report titles through independent MCP investigations."""
import argparse
import asyncio
import hashlib
import itertools
import json
from pathlib import Path

from fivewhys.desk.engine import investigate
from fivewhys.pipeline import DEFAULT_POSTMORTEM_DIR


async def run(output):
    sources = {}
    for path in sorted(DEFAULT_POSTMORTEM_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        sources[path.stem] = (text.splitlines()[0].removeprefix("# 장애 보고서: "), text)
    results = []
    for left, right in itertools.combinations(sources, 2):
        question = f"‘{sources[left][0]}’ 및 ‘{sources[right][0]}’ 두 보고서의 근본 원인을 비교해 주세요."
        record = await investigate(question)
        citations = record["citations"]
        ids = [c["id"] for c in citations]
        expected = {left, right}
        supported = set()
        for ref in citations:
            kind, doc, digest = ref["id"].split(":", 2)
            section, _, body = ref["text"].partition("\n")
            if (kind == "doc" and doc in expected and section == "근본 원인" and body.strip()
                    and body in sources[doc][1] and ref["id"] in record["answer"]
                    and hashlib.sha256(ref["text"].encode()).hexdigest()[:10] == digest):
                supported.add(doc)
        tools = [step["tool"] for step in record["steps"]]
        passed = (record["status"] == "answered" and expected == supported and len(ids) == 2
                  and tools == ["search_past_incidents", "search_past_incidents"])
        results.append({"documents":[left,right], "reason":record["reason"],
                        "citation_ids":ids, "tools":tools, "passed":passed})
    passed = sum(row["passed"] for row in results)
    output.write_text(json.dumps({"mode":"offline", "documents":len(sources), "passed":passed,
                                 "pairs":results}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"{passed}/{len(results)} pairs")
    return passed == len(results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(0 if asyncio.run(run(parser.parse_args().output)) else 1)
