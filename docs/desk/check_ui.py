"""Check archive and live inquiry flows with Playwright against a running desk API."""

import argparse
import hashlib
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse
import json
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--live-model",
    action="store_true",
    help="Submit one more question to the configured local LLM",
)
parser.add_argument("--base-url", default="http://127.0.0.1:8750")
parser.add_argument("--chromium", default=shutil.which("chromium"))
parser.add_argument(
    "--captures", type=Path, help="Write actual UI snapshots to this directory"
)
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
assets = repo / "desk-demo"


def capture(page, name, full=True):
    if args.captures:
        args.captures.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=args.captures / name, full_page=full)


runs = json.loads((assets / "runs.json").read_text())
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=args.chromium, args=["--no-sandbox", "--disable-dev-shm-usage"]
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, locale="ko-KR")
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))

    def mount(route):
        name = Path(urlparse(route.request.url).path).name or "index.html"
        if name == "desk":
            name = "index.html"
        route.fulfill(path=assets / name)

    url = args.base_url.rstrip("/") + "/five-whys-agent/desk/"
    page.route("**/five-whys-agent/desk/**", mount)
    page.goto(url)
    active = next(
        (
            run
            for run in runs
            if run["status"] == "answered"
            and run.get("evaluation_passed")
            and run.get("model_usage", {}).get("model")
            and re.search("[가-힣]", run["question"])
        ),
        runs[0],
    )
    expect(page.locator("#record-id")).to_have_text(active["id"])
    if active.get("model_usage"):
        expect(page.locator("#metadata")).to_contain_text(
            active["model_usage"]["model"], ignore_case=True
        )
    expect(page.locator(".paper-index")).to_have_text(f"{len(runs)}건")
    expect(page.locator("#live")).to_be_hidden()
    expect(page.locator("#step-count")).to_have_text(str(len(active["steps"])))
    print(
        "Archive SHA-256",
        hashlib.sha256((assets / "runs.json").read_bytes()).hexdigest(),
    )
    print(
        "Chromium",
        browser.version,
        "records",
        len(runs),
        "initial record",
        active["id"],
    )
    capture(page, "desktop.png")
    page.locator("#plan summary").click()
    expect(page.locator("#plan-input")).to_contain_text(active["plan"][0]["tool"])
    page.locator(".cite-link").nth(1).click()
    assert page.locator("#evidence-2").evaluate("d=>d.open")
    page.locator(".step summary").first.click()
    expect(page.get_by_text("반환값", exact=True).first).to_be_visible()
    page.locator("#open-library").click()
    page.locator("#query").fill("존재하지않는질문")
    expect(page.locator("#matches")).to_contain_text("일치하는 기록이 없습니다")
    page.locator("#query").fill("")
    page.get_by_role("button", name="판단 보류", exact=True).click()
    fail = next(r for r in runs if r["status"] == "withheld" and r["steps"])
    page.locator("#query").fill(fail["id"])
    page.locator(".choice").first.click()
    expect(page.locator("#record-id")).to_have_text(fail["id"])
    expect(page.locator("#verdict")).to_have_text("판단 보류")
    expect(page.locator("#citation-count")).to_have_text(str(len(fail["citations"])))
    print(
        "PASS desktop real record, trace, citation navigation, search/filter, withheld"
    )
    page.set_viewport_size({"width": 390, "height": 844})
    page.reload()
    expect(page.locator("#report")).to_be_visible()
    capture(page, "mobile.png")
    page.locator("#open-library").click()
    capture(page, "mobile-selection.png", full=False)
    page.keyboard.press("Escape")
    expect(page.locator("#library")).to_be_hidden()
    for width in (320, 375, 390, 768, 1440):
        page.set_viewport_size({"width": width, "height": 844})
        page.locator(".step summary").first.evaluate("s=>s.parentElement.open=true")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (
            f"overflow at {width}"
        )
    print("PASS five viewport widths, long tool output, Escape")
    held = []
    page.route("**/runs.json", lambda route: held.append(route))
    page.reload(wait_until="domcontentloaded")
    expect(page.locator("#loading")).to_have_text("조사 기록을 불러오는 중입니다.")
    assert held, "Expected an intercepted archive response"
    held[0].fulfill(status=503, body="down")
    expect(page.get_by_role("button", name="다시 시도")).to_be_visible()
    page.unroute("**/runs.json")
    page.get_by_role("button", name="다시 시도").click()
    expect(page.locator("#report")).to_be_visible()
    page.route("**/runs.json", lambda route: route.fulfill(json=[]))
    page.reload()
    expect(page.locator("#loading")).to_contain_text("아직 저장된")
    page.unroute("**/runs.json")
    print("PASS loading, archive failure/retry and empty archive")
    page.goto(args.base_url.rstrip("/") + "/desk/")
    page.locator("#live summary").click()
    page.locator("#question").fill(
        "주문 API 장애에 대한 배포와 로그 근거, 과거 커넥션 풀 사례를 확인해 주세요."
    )
    page.locator("#live-form button[type=submit]").click()
    expect(page.locator("#record-mode")).to_have_text("새 질문 실행", timeout=120000)
    expect(page.locator("#verdict")).to_have_text("답변")
    capture(page, "local-inquiry.png")
    print(
        "PASS local HTTP POST/queue/poll/result and evidence",
        page.locator("#record-id").inner_text(),
    )
    if args.live_model:
        page.locator("#engine").select_option("local")
        previous_id = page.locator("#record-id").inner_text()
        page.locator("#question").fill(active["question"])
        page.locator("#live-form button[type=submit]").click()
        expect(page.locator("#record-id")).not_to_have_text(previous_id, timeout=120000)
        expect(page.locator("#metadata")).to_contain_text("Qwen2.5-1.5B-Instruct")
        expect(page.locator("#verdict")).to_have_text("답변")
        expect(page.locator("#step-count")).to_have_text("3")
        print(
            "PASS live Qwen planner, separate job, model identity, 3 actual tool calls"
        )
    assert not errors, errors
    browser.close()
