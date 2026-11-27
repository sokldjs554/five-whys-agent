"use strict";

const byId = (id) => document.getElementById(id);
const library = byId("library");
const query = byId("query");
const report = byId("report");
const loadNotice = byId("loading");
const archiveButton = byId("open-library");
const runtimeLabel = {
  "langgraph+mcp-stdio/model": "모델 계획",
  "langgraph+mcp-stdio/offline": "규칙 기반",
};
const statusLabel = { answered: "답변", withheld: "판단 보류" };
const engineLabel = { rules: "규칙 기반", local: "로컬 모델" };
const reasonLabel = {
  verified: "변경 기록과 로그, 과거 보고서를 대조했습니다.",
  insufficient_evidence: "결론을 뒷받침할 근거가 부족합니다.",
  out_of_scope: "현재 자료로 조사할 수 있는 질문의 범위를 벗어났습니다.",
  conflict: "도구가 반환한 자료 사이에 충돌이 있습니다.",
  invalid_result: "반환된 자료의 형식을 검증하지 못했습니다.",
};
let runs = [];
let filter = "all";

function element(tag, className, value) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (value !== undefined) node.textContent = String(value);
  return node;
}

function badge(status, small = false) {
  return element(
    "span",
    (small ? "mini-status " : "badge ") + status,
    statusLabel[status],
  );
}

function validRun(run) {
  return (
    run &&
    typeof run.id === "string" &&
    typeof run.question === "string" &&
    Object.hasOwn(statusLabel, run.status) &&
    Array.isArray(run.steps) &&
    Array.isArray(run.citations)
  );
}

function renderChoices() {
  const words = query.value
    .trim()
    .normalize("NFKC")
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean);
  const found = runs.filter((run) => {
    const content = [
      run.title || "",
      run.question,
      run.id,
      ...run.steps.map((step) => step.tool),
    ]
      .join(" ")
      .normalize("NFKC")
      .toLowerCase();
    return (
      (filter === "all" || run.status === filter) &&
      words.every((word) => content.includes(word))
    );
  });
  byId("matches").textContent = found.length
    ? `저장된 기록 ${found.length}건`
    : "일치하는 기록이 없습니다. 다른 검색어나 상태를 선택하세요.";
  const choices = found.map((run) => {
    const button = element("button", "choice");
    button.type = "button";
    const meta = element("span", "choice-meta");
    meta.append(badge(run.status, true), element("span", "code", run.id));
    button.append(
      meta,
      element("span", "choice-question", run.title || run.question),
    );
    if (run.title)
      button.append(element("span", "choice-preview", run.question));
    button.addEventListener("click", () => {
      library.close();
      selectRun(run, "저장된 실행", true);
    });
    return button;
  });
  byId("choices").replaceChildren(...choices);
}

archiveButton.addEventListener("click", () => {
  renderChoices();
  library.showModal();
  query.focus();
});
byId("close-library").addEventListener("click", () => library.close());
library.addEventListener("click", (event) => {
  if (event.target !== library) return;
  const bounds = library.getBoundingClientRect();
  if (
    event.clientX < bounds.left ||
    event.clientX > bounds.right ||
    event.clientY < bounds.top ||
    event.clientY > bounds.bottom
  )
    library.close();
});
query.addEventListener("input", renderChoices);
byId("filters").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-filter]");
  if (!button) return;
  filter = button.dataset.filter;
  for (const item of byId("filters").querySelectorAll("button"))
    item.setAttribute("aria-pressed", String(item === button));
  renderChoices();
});

function meta(label, value) {
  const node = element("span");
  node.append(label, element("strong", "", value));
  return node;
}

function addAnswer(record) {
  const box = byId("answer");
  box.replaceChildren();
  const citations = new Map(
    record.citations.map((citation, index) => [citation.id, index]),
  );
  if (record.answer) {
    const answer = element("p", "content-text");
    for (const part of record.answer.split(/(\[[^\]\n]+\])/g)) {
      const index = part.startsWith("[")
        ? citations.get(part.slice(1, -1))
        : undefined;
      if (index === undefined) {
        answer.append(part);
        continue;
      }
      const link = element("a", "cite-link", `근거 ${index + 1}`);
      link.href = `#evidence-${index + 1}`;
      link.title = record.citations[index].id;
      link.addEventListener("click", (event) => {
        event.preventDefault();
        const target = byId(`evidence-${index + 1}`);
        target.open = true;
        target.querySelector("summary").focus();
        target.scrollIntoView({ block: "nearest" });
      });
      answer.append(link);
    }
    box.append(answer);
  }
  if (
    record.reason &&
    (record.status === "withheld" || record.reason !== "verified")
  ) {
    const reason = element("div", record.answer ? "reason" : "");
    if (record.answer) {
      reason.append(element("span", "code", "사유 코드  " + record.reason));
    } else {
      reason.append(
        element("h4", "reason-label", "보류 사유"),
        element(
          "p",
          "content-text",
          reasonLabel[record.reason] || record.reason,
        ),
      );
    }
    box.append(reason);
  }
  if (!box.childNodes.length)
    box.append(element("p", "hint", "저장된 답변 내용이 없습니다."));
}

const citationKinds = { change: "변경 기록", log: "로그", doc: "과거 보고서" };
function addCitations(items) {
  const box = byId("citations");
  byId("citation-count").textContent = String(items.length);
  if (!items.length) {
    box.replaceChildren(
      element("p", "empty-evidence", "이 실행에서 인용한 원문이 없습니다."),
    );
    return;
  }
  const list = element("ol", "citation-list");
  items.forEach((item, index) => {
    const entry = element("li");
    const details = element("details", "citation");
    details.id = `evidence-${index + 1}`;
    details.open = index === 0;
    const summary = element("summary");
    summary.append(
      element("span", "cite-no", `근거 ${index + 1}`),
      element("strong", "", item.title || citationKinds[item.id.split(":")[0]] || "원문"),
    );
    details.append(
      summary,
      element("p", "citation-text", item.text),
      element("p", "source-path", item.source),
      element("p", "cite-id", item.id),
    );
    entry.append(details);
    list.append(entry);
  });
  box.replaceChildren(list);
}

function payload(value) {
  if (value === undefined) return "기록 없음";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}
function argument(label, value) {
  const box = element("div", "argument");
  const pre = element("pre", "", payload(value));
  pre.tabIndex = 0;
  pre.setAttribute("aria-label", label);
  box.append(element("h4", "", label), pre);
  return box;
}
function addTrace(steps) {
  byId("step-count").textContent = String(steps.length);
  const entries = steps.map((step, index) => {
    const entry = element("li", "step");
    const details = element("details");
    const summary = element("summary");
    const name = element("span", "tool-detail");
    name.append(element("span", "tool-name", step.tool));
    if (typeof step.input?.query === "string" && step.input.query) {
      const scope = step.input.doc ? `${step.input.doc} · ${step.input.section}` : step.input.query;
      name.append(element("span", "tool-query", scope));
    }
    const returned =
      step.status === "ok" && Array.isArray(step.output)
        ? `${step.output.length}건 반환`
        : step.status;
    const status = element("span", "step-status", returned || "");
    if (step.status && step.status !== "ok")
      status.classList.add("failed-step");
    summary.append(
      element("span", "step-number", String(index + 1).padStart(2, "0")),
      name,
      status,
    );
    details.append(
      summary,
      argument("입력", step.input),
      argument("반환값", step.output),
    );
    entry.append(details);
    return entry;
  });
  if (!entries.length)
    entries.push(
      element("li", "empty-evidence", "기록된 도구 호출이 없습니다."),
    );
  byId("trace-list").replaceChildren(...entries);
}

function selectRun(run, mode, focus = false) {
  byId("record-mode").textContent = mode;
  byId("record-id").textContent = run.id;
  byId("report-title").textContent = run.title || run.question;
  const original = byId("original-question");
  original.hidden = !run.title;
  original.textContent = run.title ? run.question : "";
  const note = byId("evaluation-note");
  const notes = [];
  if (run.fixture)
    notes.push(
      "시험 조건 · " +
        ({
          conflicting_deployments: "충돌하는 배포 기록 주입",
          tool_error: "도구 오류 주입",
          tool_timeout: "도구 타임아웃 주입",
        }[run.fixture] || run.fixture),
    );
  if (run.evaluation_passed === false)
    notes.push("이 실행은 평가 문항의 채점 기준을 충족하지 못했습니다.");
  note.textContent = notes.join(" / ");
  note.hidden = !notes.length;
  const displayEngine = runtimeLabel[run.engine] || engineLabel[run.engine];
  byId("metadata").replaceChildren(
    meta(
      "엔진",
      displayEngine
        ? `${displayEngine} · ${run.engine}`
        : run.engine || "기록 없음",
    ),
    meta(
      "모델 호출",
      run.model_calls == null ? "미기록" : `${run.model_calls}회`,
    ),
    meta("도구 호출", `${run.steps.length}회`),
  );
  if (run.model_usage?.model) {
    const model = run.model_usage.model;
    const name =
      model === "qwen2.5-1.5b-instruct" ? "Qwen2.5-1.5B-Instruct" : model;
    byId("metadata").append(meta("모델", name));
  }
  const verdict = byId("verdict");
  verdict.className = "badge " + run.status;
  verdict.textContent = statusLabel[run.status];
  addAnswer(run);
  addCitations(run.citations);
  addTrace(run.steps);
  const plan = byId("plan");
  plan.open = false;
  plan.hidden = !Array.isArray(run.plan) || !run.plan.length;
  byId("plan-input").textContent = plan.hidden ? "" : payload(run.plan);
  const originalPlan = byId("original-plan");
  originalPlan.open = false;
  originalPlan.hidden = !Array.isArray(run.proposed_plan);
  byId("original-plan-input").textContent = originalPlan.hidden ? "" : payload(run.proposed_plan);
  const planning = byId("plan-metadata");
  planning.replaceChildren();
  const usage = run.model_usage;
  if (usage?.backend) planning.append(meta("백엔드", usage.backend));
  if (Number.isInteger(usage?.prompt_tokens))
    planning.append(meta("입력 토큰", usage.prompt_tokens));
  if (Number.isInteger(usage?.completion_tokens))
    planning.append(meta("출력 토큰", usage.completion_tokens));
  if (Number.isFinite(usage?.elapsed_ms))
    planning.append(meta("모델 요청 시간", `${usage.elapsed_ms} ms`));
  report.hidden = false;
  if (focus) {
    report.focus();
    byId("announcement").textContent =
      `${mode} 열림. ${statusLabel[run.status]}.`;
  }
}

async function loadArchive() {
  loadNotice.hidden = false;
  loadNotice.textContent = "조사 기록을 불러오는 중입니다.";
  try {
    const response = await fetch("./runs.json");
    if (!response.ok) throw new Error("load");
    const records = await response.json();
    if (!Array.isArray(records) || !records.every(validRun))
      throw new Error("format");
    runs = records;
    document.querySelector(".paper-index").textContent = `${runs.length}건`;
    if (!runs.length) {
      loadNotice.textContent = "아직 저장된 조사 기록이 없습니다.";
      return;
    }
    archiveButton.disabled = false;
    loadNotice.hidden = true;
    const preferred = runs.find(
      (run) =>
        run.status === "answered" &&
        run.evaluation_passed === true &&
        run.model_usage?.model &&
        /[가-힣]/.test(run.question),
    );
    const requested = new URLSearchParams(location.search).get("run");
    const linked = runs.find((run) => run.id === requested);
    selectRun(linked || preferred || runs[0], "저장된 실행");
  } catch {
    loadNotice.textContent = "조사 기록을 불러오지 못했습니다.";
    const retry = element("button", "primary", "다시 시도");
    retry.addEventListener("click", loadArchive);
    loadNotice.append(retry);
  }
}

async function checkLiveMode() {
  if (!/^\/desk\/(?:index\.html)?$/.test(location.pathname)) return;
  try {
    const response = await fetch("/desk/config");
    if (!response.ok) return;
    const config = await response.json();
    if (config.mode !== "live" || !Array.isArray(config.engines)) return;
    const engines = config.engines.filter((item) =>
      Object.hasOwn(engineLabel, item),
    );
    if (!engines.length) return;
    byId("engine").replaceChildren(
      ...engines.map((item) => new Option(engineLabel[item], item)),
    );
    if (Number.isInteger(config.max_question_length))
      byId("question").maxLength = config.max_question_length;
    byId("live").hidden = false;
  } catch {
    /* The static archive remains available when the API is offline. */
  }
}

const liveStatus = byId("live-status");
const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));
const phaseLabels = {
  queued: "조사 대기 중입니다.",
  running: "도구를 호출해 조사하고 있습니다.",
};

async function checkJob(id) {
  const path = "/desk/jobs/" + encodeURIComponent(id);
  while (true) {
    const response = await fetch(path, { cache: "no-store" });
    if (!response.ok)
      throw new Error(`상태 확인 실패 (HTTP ${response.status})`);
    const job = await response.json();
    if (["completed", "withheld", "failed"].includes(job.status)) {
      const result = await fetch(path + "/result", { cache: "no-store" });
      if (!result.ok) throw new Error(`결과 확인 실패 (HTTP ${result.status})`);
      const record = await result.json();
      if (!validRun(record))
        throw new Error("결과의 형식을 확인할 수 없습니다.");
      selectRun(record, "새 질문 실행", true);
      liveStatus.textContent =
        job.status === "failed"
          ? "조사가 중단되었습니다. 조사 결과에서 이유를 확인하세요."
          : "조사를 마쳤습니다.";
      return;
    }
    if (!Object.hasOwn(phaseLabels, job.status))
      throw new Error("알 수 없는 조사 상태입니다.");
    liveStatus.textContent = phaseLabels[job.status];
    await sleep(800);
  }
}
async function watchJob(id, submit) {
  submit.disabled = true;
  try {
    await checkJob(id);
  } catch (error) {
    liveStatus.textContent = error.message + " ";
    const retry = element("button", "retry", "같은 조사 다시 확인");
    retry.type = "button";
    retry.onclick = () => {
      retry.remove();
      watchJob(id, submit);
    };
    liveStatus.append(retry);
  } finally {
    submit.disabled = false;
  }
}
byId("live-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = event.currentTarget.querySelector("button[type=submit]");
  const field = byId("question");
  if (field.value.trim().length < 2) {
    field.setCustomValidity("질문을 두 글자 이상 입력하세요.");
    field.reportValidity();
    return;
  }
  submit.disabled = true;
  liveStatus.textContent = "질문을 접수하고 있습니다.";
  let job;
  try {
    const response = await fetch("/desk/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question: field.value.trim(),
        engine: byId("engine").value,
      }),
    });
    if (!response.ok)
      throw new Error(
        response.status === 429
          ? "대기열이 가득 찼습니다. 잠시 뒤 다시 시도하세요."
          : `질문 접수 실패 (HTTP ${response.status})`,
      );
    job = await response.json();
    if (!job.id) throw new Error("접수 번호를 확인할 수 없습니다.");
  } catch (error) {
    liveStatus.textContent = error.message;
    submit.disabled = false;
    return;
  }
  await watchJob(job.id, submit);
});
byId("question").addEventListener("input", () =>
  byId("question").setCustomValidity(""),
);
loadArchive();
checkLiveMode();
