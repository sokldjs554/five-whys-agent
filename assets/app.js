"use strict";
const el = id => document.getElementById(id);
const kinds = {log: "로그", deployment: "배포", report: "사고 보고서", runbook: "운영 지침"};
const states = {queued: "대기 중", running: "분석 중", completed: "분석 완료", failed: "분석 실패"};
const deliveries = {
  disabled: "콜백 미사용", pending: "전송 대기", retrying: "전송 실패 · 재시도 대기",
  delivered: "결과 전달 완료", exhausted: "자동 재시도 종료"
};
const kstTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
});

function node(tag, className, text) {
  const item = document.createElement(tag);
  if (className) item.className = className;
  if (text !== undefined && text !== null) item.textContent = String(text);
  return item;
}

function details(label, child, className = "technical") {
  const section = node("details", className);
  section.append(node("summary", "", label), child);
  return section;
}

function values(pairs) {
  const list = node("dl", "key-values");
  for (const [label, value] of pairs) {
    if (value === null || value === undefined || value === "") continue;
    const row = node("div");
    row.append(node("dt", "", label), node("dd", "", value));
    list.append(row);
  }
  return list;
}

function clock(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : kstTime.format(date);
}

function renderJob() {
  const job = state.job;
  const status = job?.status;
  el("status").textContent = states[status] || "기록 열기 전";
  el("status").dataset.state = status || "";
  el("engine-tag").textContent = "Scripted";
  el("findings-jump").hidden = !state.result;
  el("llm-count").textContent = job?.llm_calls ?? "—";
  el("hyp-count").textContent = state.result?.hypotheses?.length ?? "—";
  el("ev-count").textContent = state.result?.evidence?.length ?? "—";
  const info = el("job-info");
  if (!job) {
    info.replaceChildren(node("p", "sub", "실행 후 작업 ID와 처리 상태를 확인할 수 있습니다."));
  } else {
    const meta = values([
      ["작업 ID", job.id], ["팀", job.team], ["처리 상태", job.status],
      ["접수 (KST)", clock(job.created_at)], ["시작 (KST)", clock(job.started_at)],
      ["종료 (KST)", clock(job.finished_at)], ["엔진 턴", state.result?.engine_turns],
      ["오류", job.error]
    ]);
    // Update the metadata without closing a disclosure the reader has already opened.
    const json = info.querySelector("details");
    const raw = node("pre", "", JSON.stringify({job, result: state.result}, null, 2));
    const expander = details("저장된 API 응답 JSON", raw);
    expander.open = json?.open || false;
    info.replaceChildren(meta, expander);
  }
  const callback = job?.callback_status;
  el("callback-status").textContent = deliveries[callback] || "전송 전";
  el("callback-status").dataset.state = callback || "";
  const attempts = job?.callbacks || [];
  el("callback-count").textContent = attempts.length;
  const history = el("callback-history");
  history.replaceChildren();
  if (attempts.length) {
    const list = node("ol", "attempt-list");
    for (const item of attempts) {
      const code = item.status_code == null ? "응답 없음" : "HTTP " + item.status_code;
      const time = clock(item.created_at);
      list.append(node("li", "", [code, time && time + " KST", item.error !== code && item.error].filter(Boolean).join(" · ")));
    }
    history.append(list);
  } else {
    history.append(node("p", "sub", "전송 기록이 아직 없습니다."));
  }
  if (state.beforeRetry !== null && state.beforeRetry !== undefined) {
    history.append(node("p", "note", "LLM 호출 · 재전송 전 " + state.beforeRetry +
      "회 / 현재 " + (job?.llm_calls ?? "—") + "회"));
  }
  controls();
}

function evidenceTitle(evidence) {
  return evidence?.title || evidence?.source || evidence?.id || "근거";
}

function evidenceButton(evidence, className = "source-link", label) {
  const button = node("button", className, label || evidenceTitle(evidence));
  button.type = "button";
  button.dataset.evidence = evidence.id;
  button.addEventListener("click", () => openEvidence(evidence.id));
  return button;
}

function renderHypotheses(result, lookup) {
  const target = el("hypotheses");
  target.replaceChildren();
  if (!result?.hypotheses?.length) {
    target.append(node("p", "empty", result ? "이 조사에서 제시한 원인 가설이 없습니다." :
      "질문을 실행하면 원인 가설과 인용 근거를 볼 수 있습니다."));
    return;
  }
  for (const hypothesis of result.hypotheses) {
    const article = node("article", "hypothesis");
    article.append(node("h3", "", hypothesis.title), node("p", "", hypothesis.description));
    const citations = node("div", "citations");
    for (const id of hypothesis.evidence_ids || []) {
      const evidence = lookup.get(id);
      if (evidence) citations.append(evidenceButton(evidence, "citation",
        (kinds[evidence.kind] || "근거") + " · " + evidenceTitle(evidence)));
    }
    if (citations.childElementCount) article.append(citations);
    if (hypothesis.paths?.length) {
      const paths = node("div");
      for (const path of hypothesis.paths) paths.append(graphPath(path, lookup));
      article.append(details("인용 근거의 그래프 경로 · " + hypothesis.paths.length + "건", paths));
    }
    target.append(article);
  }
}

function renderTimeline(result) {
  const target = el("timeline");
  const rows = (result?.evidence || []).filter(item =>
    item.observed_at && ["log", "deployment"].includes(item.kind));
  rows.sort((a, b) => Date.parse(a.observed_at) - Date.parse(b.observed_at));
  if (!rows.length) {
    target.replaceChildren(node("p", "empty small", result ?
      "조회된 근거 중 시각이 기록된 배포 또는 로그가 없습니다." : "확인한 사건이 아직 없습니다."));
    return;
  }
  const list = node("ol", "timeline");
  for (const item of rows) {
    const row = node("li");
    const start = clock(item.observed_at);
    const end = clock(item.end_at);
    const time = node("time", "", start + (end && end !== start ? "\n– " + end : ""));
    time.dateTime = item.observed_at;
    const event = node("div", "event");
    event.append(evidenceButton(item), node("div", "event-meta",
      [kinds[item.kind], item.service, "KST"].filter(Boolean).join(" · ")));
    row.append(time, event);
    list.append(row);
  }
  target.replaceChildren(list);
}

function ranking(title, entries, other, decisions) {
  const section = node("section", "ranking");
  section.append(node("h3", "", title + " · " + entries.length + "건"));
  const list = node("ol");
  for (const entry of entries) {
    const row = node("li");
    const content = node("div");
    content.append(evidenceButton(entry), node("span", "kind-tag",
      [kinds[entry.kind] || entry.kind, other.has(entry.id) ? "공통 근거" : "이 검색에서만 선택"].join(" · ")));
    const decision = decisions.get(entry.id);
    if (decision) {
      const label = decision.action === "excluded" ? "제외 이유" : "선택 이유";
      content.append(node("p", "rank-reason", label + " · " + decision.reason));
    }
    row.append(content);
    list.append(row);
  }
  section.append(entries.length ? list : node("p", "sub", "선택된 근거가 없습니다."));
  return section;
}

function graphPath(path, lookup) {
  const title = id => lookup.has(id) ? evidenceTitle(lookup.get(id)) : id;
  const content = node("div");
  // Neo4j traversal can follow a relationship in reverse. Preserve its stored direction.
  if (path.edges?.length) {
    const edges = path.incident_edge ? [...path.edges, path.incident_edge] : path.edges;
    for (const edge of edges) content.append(node("p", "path-line",
      title(edge.source) + " —[" + edge.type + "]→ " + title(edge.target)));
  } else {
    const readable = (path.nodes || []).map((id, i) =>
      i === 0 ? title(id) : " —[" + (path.relations?.[i-1] || "관계") + "]— " + title(id)).join("");
    content.append(node("p", "path-line", readable));
  }
  const evidence = lookup.get(path.evidence_id);
  if (evidence) content.append(evidenceButton(evidence, "source-link", "이 경로의 근거 원문"));
  return details(title(path.evidence_id), content, "path-detail");
}

function renderComparison(result, lookup) {
  const target = el("compare-content");
  if (!result) {
    target.replaceChildren(node("p", "empty", "조사 후 두 검색의 근거 순위와 그래프 경로를 비교할 수 있습니다."));
    return;
  }
  const vectors = result.vector || [];
  const graphs = result.graph || [];
  const v = new Set(vectors.map(e => e.id));
  const g = new Set(graphs.map(e => e.id));
  const common = [...v].filter(id => g.has(id)).length;
  const added = g.size - common;
  const removed = v.size - common;
  const sameOrder = vectors.every((e, i) => graphs[i]?.id === e.id);
  const summary = added || removed ? "그래프 검색에서 근거 " + added + "건이 추가되고 " + removed + "건이 제외됐습니다."
    : (sameOrder ? "두 검색이 같은 근거를 같은 순서로 선택했습니다." : "선택된 근거는 같고 순위가 달라졌습니다.");
  const grid = node("div", "compare-grid");
  const decisions = new Map((result.decisions || []).map(item => [item.evidence_id, item]));
  const excluded = new Map([...decisions].filter(([, decision]) => decision.action === "excluded"));
  const retained = new Map([...decisions].filter(([, decision]) => decision.action === "retained"));
  grid.append(ranking("벡터 단독", vectors, g, excluded), ranking("벡터 + 그래프", graphs, v, retained));
  target.replaceChildren(node("p", "compare-summary", summary + " 공통 근거 " + common + "건."), grid);
  const paths = result.paths || [];
  const pathsBlock = node("div", "paths");
  pathsBlock.append(node("h3", "", "그래프 경로 · " + paths.length + "건"));
  if (!paths.length) pathsBlock.append(node("p", "sub", "검색에서 반환한 관계 경로가 없습니다."));
  for (const path of paths) pathsBlock.append(graphPath(path, lookup));
  target.append(pathsBlock);
}

function renderResult() {
  const result = state.result;
  const lookup = new Map([...(result?.vector || []), ...(result?.graph || []),
    ...(result?.evidence || [])].map(item => [item.id, item]));
  renderHypotheses(result, lookup);
  renderTimeline(result);
  renderComparison(result, lookup);
}

async function openEvidence(id) {
  if (!state.job) return;
  const generation = state.generation;
  const sequence = ++state.sourceSequence;
  const dialog = el("source-dialog");
  el("source-heading").textContent = "근거 원문";
  el("source-content").replaceChildren(node("p", "sub", "원문을 불러오는 중입니다."));
  if (!dialog.open) dialog.showModal();
  try {
    const evidence = state.record.sources[id];
    if (!(generation === state.generation) || state.sourceSequence !== sequence || !dialog.open) return;
    el("source-heading").textContent = evidenceTitle(evidence);
    const meta = values([["유형", kinds[evidence.kind] || evidence.kind], ["서비스", evidence.service],
      ["출처", evidence.source], ["원문 위치", evidence.locator]]);
    el("source-content").replaceChildren(meta, node("pre", "source-text", evidence.text),
      details("버전과 근거 식별 정보", values([["버전", evidence.version],
        ["근거 ID", evidence.id], ["시작 시각", evidence.observed_at],
        ["종료 시각", evidence.end_at]])));
  } catch (error) {
    if ((generation === state.generation) && sequence === state.sourceSequence)
      el("source-content").replaceChildren(node("p", "sub", "원문을 열 수 없습니다. " + error.message));
  }
}


const state = {generation: 0, sourceSequence: 0, record: null, result: null, job: null, beforeRetry: null};

function controls() {
  el("run").disabled = !state.record;
  el("retry").disabled = state.job?.callback_status !== "retrying";
}

async function loadTeam() {
  const generation = ++state.generation;
  state.record = state.result = state.job = state.beforeRetry = null;
  if (el("source-dialog").open) el("source-dialog").close();
  el("job-details").open = el("callback-details").open = false;
  el("notice").hidden = el("reconnect").hidden = true;
  renderJob();
  renderResult();
  try {
    const team = el("team").value;
    const response = await fetch("./records/" + (team === "platform" ? "platform" : "orders") + ".json");
    if (!response.ok) throw new Error(String(response.status));
    const record = await response.json();
    if (generation !== state.generation) return;
    state.record = record;
    el("question").value = record.question;
    controls();
  } catch {
    if (generation !== state.generation) return;
    el("notice").textContent = "조사 기록을 불러오지 못했습니다.";
    el("notice").hidden = el("reconnect").hidden = false;
  }
}

el("ask-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!state.record) return;
  state.job = state.record.beforeRetry;
  state.result = state.record.result;
  state.beforeRetry = null;
  renderResult();
  renderJob();
});
el("retry").addEventListener("click", () => {
  if (el("retry").disabled) return;
  state.beforeRetry = state.job.llm_calls;
  state.job = state.record.afterRetry;
  el("callback-details").open = true;
  renderJob();
});
el("team").addEventListener("change", loadTeam);
el("reconnect").addEventListener("click", loadTeam);
el("source-close").addEventListener("click", () => el("source-dialog").close());
el("source-dialog").addEventListener("click", event => {
  if (event.target !== el("source-dialog")) return;
  const r = el("source-dialog").getBoundingClientRect();
  if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)
    el("source-dialog").close();
});

function highlightTab() {
  const active = document.querySelector('.section-nav a[href="' +
    (["#findings","#comparison","#delivery"].includes(location.hash) ? location.hash : "#ask") + '"]');
  document.querySelectorAll(".section-nav a").forEach(link => link.removeAttribute("aria-current"));
  active.setAttribute("aria-current", "location");
}
window.addEventListener("hashchange", highlightTab);
highlightTab();
loadTeam();
