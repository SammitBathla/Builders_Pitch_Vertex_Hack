"use strict";

/* ---------- API helpers ---------- */

async function api(path, opts) {
  const res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  if (!res.ok) {
    let detail = res.statusText;
    try { const body = await res.json(); detail = body.detail || JSON.stringify(body); } catch (e) {}
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}
const apiGet = (path) => api(path);
const apiPost = (path, body) => api(path, { method: "POST", body: JSON.stringify(body || {}) });
const apiPut = (path, body) => api(path, { method: "PUT", body: JSON.stringify(body || {}) });

/* ---------- Status bar ---------- */

const statusBar = document.getElementById("status-bar");
function setStatus(message, kind) {
  statusBar.textContent = message || "";
  statusBar.className = "status-bar" + (kind ? " " + kind : "");
}
function setBusy(message) { setStatus(message, "busy"); }
function setError(message) { setStatus(message, "error"); }
function clearStatus() { setStatus("", ""); }

async function withBusy(message, fn) {
  setBusy(message);
  try {
    const result = await fn();
    clearStatus();
    return result;
  } catch (e) {
    setError(e.message || String(e));
    throw e;
  }
}

/* ---------- Simple view router ---------- */

const views = ["dashboard", "investigation", "audit"];
function showView(name) {
  for (const v of views) {
    document.getElementById("view-" + v).hidden = (v !== name);
  }
  document.querySelectorAll(".nav-link[data-route]").forEach((btn) => {
    if (btn.dataset.route === name) btn.setAttribute("aria-current", "page");
    else btn.removeAttribute("aria-current");
  });
}

document.querySelectorAll(".nav-link[data-route]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const route = btn.dataset.route;
    showView(route);
    if (route === "dashboard") loadDashboard();
    if (route === "audit") loadAudit();
  });
});
document.getElementById("back-to-dashboard").addEventListener("click", () => {
  showView("dashboard");
  loadDashboard();
});

/* ---------- Assumptions dialog ---------- */

const assumptionsDialog = document.getElementById("assumptions-dialog");
document.getElementById("assumptions-btn").addEventListener("click", async () => {
  try {
    const cfg = await apiGet("/api/config");
    const list = document.getElementById("assumptions-list");
    list.innerHTML = "";
    cfg.assumptions.forEach((a) => {
      const li = document.createElement("li");
      li.textContent = a;
      list.appendChild(li);
    });
    assumptionsDialog.showModal();
  } catch (e) { setError(e.message); }
});
document.getElementById("close-assumptions").addEventListener("click", () => assumptionsDialog.close());

/* ---------- Formatting helpers ---------- */

function fmtNum(n, digits) {
  if (n === null || n === undefined) return "—";
  return Number(n).toFixed(digits === undefined ? 2 : digits);
}
function esc(s) {
  const d = document.createElement("div");
  d.textContent = s === null || s === undefined ? "" : String(s);
  return d.innerHTML;
}

function categoryBadge(category) {
  return `<span class="badge category-${esc(category)}">${category === "Certain" || category === "Probable" ? "&#10003; " : category === "Unlikely" ? "&#10007; " : category === "Unassessable" ? "&#63; " : "&#9679; "}${esc(category)}</span>`;
}

function sourceBadge(source) {
  if (source === "override") return `<span class="badge badge-override">&#9998; Human override</span>`;
  return `<span class="badge badge-rule">&#9881; Rule-derived</span>`;
}

/* ================= DASHBOARD ================= */

async function loadDashboard() {
  const tbody = document.getElementById("signals-tbody");
  tbody.innerHTML = `<tr><td colspan="8">Loading signals…</td></tr>`;
  try {
    const { signals } = await withBusy("Loading flagged signals…", () => apiGet("/api/signals"));
    tbody.innerHTML = "";
    if (signals.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8">No flagged signals found.</td></tr>`;
    }
    signals.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${esc(s.drug)}</td>
        <td>${esc(s.event)}</td>
        <td>${s.a}</td>
        <td>${fmtNum(s.prr)}</td>
        <td>${s.ror !== null ? `${fmtNum(s.ror)} (${fmtNum(s.ror_ci_low)}–${fmtNum(s.ror_ci_high)})` : "—"}</td>
        <td>${fmtNum(s.chi_square)}</td>
        <td><button type="button" class="link-button table-btn" data-drug="${esc(s.drug)}" data-event="${esc(s.event)}">2&times;2 table</button></td>
        <td><button type="button" class="btn investigate-btn" data-drug="${esc(s.drug)}" data-event="${esc(s.event)}">Investigate</button></td>
      `;
      tbody.appendChild(tr);
    });
    tbody.querySelectorAll(".table-btn").forEach((btn) => {
      btn.addEventListener("click", () => showTable(btn.dataset.drug, btn.dataset.event));
    });
    tbody.querySelectorAll(".investigate-btn").forEach((btn) => {
      btn.addEventListener("click", () => startInvestigation(btn.dataset.drug, btn.dataset.event));
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="8">Failed to load signals: ${esc(e.message)}</td></tr>`;
  }

  await loadInvestigationsList();
}

async function showTable(drug, event) {
  try {
    const s = await withBusy("Loading 2×2 table…", () => apiGet(`/api/signals/table?drug=${encodeURIComponent(drug)}&event=${encodeURIComponent(event)}`));
    document.getElementById("table-dialog-title").textContent = `2×2 Contingency Table – ${drug} / ${event}`;
    document.getElementById("table-dialog-body").innerHTML = `
      <table class="data-table">
        <caption class="sr-only">2 by 2 contingency table for ${esc(drug)} and ${esc(event)}</caption>
        <thead><tr><th scope="col"></th><th scope="col">${esc(event)}</th><th scope="col">All other events</th></tr></thead>
        <tbody>
          <tr><th scope="row">${esc(drug)}</th><td>a = ${s.a}</td><td>b = ${s.b}</td></tr>
          <tr><th scope="row">All other drugs</th><td>c = ${s.c}</td><td>d = ${s.d}</td></tr>
        </tbody>
      </table>
      <p>PRR: <strong>${fmtNum(s.prr)}</strong> &middot; ROR: <strong>${fmtNum(s.ror)}</strong> (95% CI ${fmtNum(s.ror_ci_low)}&ndash;${fmtNum(s.ror_ci_high)}) &middot; &chi;&sup2;: <strong>${fmtNum(s.chi_square)}</strong></p>
      <p>${s.is_signal ? '<span class="badge badge-ok">&#10003; Meets Evans signal criteria</span>' : '<span class="badge badge-unknown">Does not meet Evans signal criteria</span>'}</p>
    `;
    document.getElementById("table-dialog").showModal();
  } catch (e) { setError(e.message); }
}
document.getElementById("close-table-dialog").addEventListener("click", () => document.getElementById("table-dialog").close());

async function loadInvestigationsList() {
  const container = document.getElementById("investigations-list");
  try {
    const { investigations } = await apiGet("/api/investigations");
    if (investigations.length === 0) {
      container.innerHTML = `<p class="hint">No investigations started yet — click "Investigate" on a signal above.</p>`;
      return;
    }
    const table = document.createElement("table");
    table.className = "data-table";
    table.innerHTML = `<caption class="sr-only">Existing investigations</caption>
      <thead><tr><th scope="col">Drug</th><th scope="col">Event</th><th scope="col">Status</th><th scope="col">Recommendation</th><th scope="col">Created</th><th scope="col">Open</th></tr></thead>
      <tbody></tbody>`;
    const tbody = table.querySelector("tbody");
    investigations.forEach((inv) => {
      const tr = document.createElement("tr");
      const statusBadge = inv.status === "signed_off"
        ? `<span class="badge badge-ok">&#10003; Signed off</span>`
        : `<span class="badge badge-unknown">&#9203; In progress</span>`;
      tr.innerHTML = `
        <td>${esc(inv.drug)}</td>
        <td>${esc(inv.event)}</td>
        <td>${statusBadge}</td>
        <td>${esc(inv.recommendation || "—")}</td>
        <td>${esc((inv.created_at || "").slice(0, 19).replace("T", " "))}</td>
        <td><button type="button" class="btn secondary open-inv-btn" data-id="${esc(inv.investigation_id)}">Open</button></td>
      `;
      tbody.appendChild(tr);
    });
    container.innerHTML = "";
    container.appendChild(table);
    container.querySelectorAll(".open-inv-btn").forEach((btn) => {
      btn.addEventListener("click", () => openInvestigation(btn.dataset.id));
    });
  } catch (e) {
    container.innerHTML = `<p>Failed to load investigations: ${esc(e.message)}</p>`;
  }
}

async function startInvestigation(drug, event) {
  try {
    const inv = await withBusy(
      `Running extraction + guardrails + causality rules for ${drug} / ${event}… this calls the LLM for every case and can take a little while.`,
      () => apiPost("/api/investigations", { drug, event, actor: "reviewer" })
    );
    renderInvestigation(inv);
    showView("investigation");
  } catch (e) { setError(e.message); }
}

async function openInvestigation(id) {
  try {
    const inv = await withBusy("Loading investigation…", () => apiGet(`/api/investigations/${id}`));
    renderInvestigation(inv);
    showView("investigation");
  } catch (e) { setError(e.message); }
}

/* ================= INVESTIGATION VIEW ================= */

let currentInvestigation = null;
let currentCaseIndex = 0;

function renderInvestigation(inv) {
  currentInvestigation = inv;
  currentCaseIndex = 0;

  const header = document.getElementById("investigation-header");
  const st = inv.stats;
  header.innerHTML = `
    <h1>${esc(inv.drug)} &ndash; ${esc(inv.event)}</h1>
    <p class="rule-meta">
      Investigation ${esc(inv.investigation_id)} &middot;
      ${inv.status === "signed_off" ? `<span class="badge badge-ok">&#10003; Signed off by ${esc(inv.signed_off_by)}</span>` : `<span class="badge badge-unknown">In progress</span>`}
      &middot; Cases: ${st.a} &middot; PRR ${fmtNum(st.prr)} &middot; &chi;&sup2; ${fmtNum(st.chi_square)}
      &middot; AI processing time: ${fmtNum(inv.ai_processing_seconds, 1)}s
    </p>
  `;

  renderCaseList();
  renderCaseDetail();
  renderRecommendation();
  renderSummary();
  renderMetrics();
  renderChatHistory([]);
  loadChatHistory(inv.investigation_id);

  setupTabs();
}

function setupTabs() {
  const tabs = [
    ["tab-btn-cases", "tab-cases"],
    ["tab-btn-summary", "tab-summary"],
    ["tab-btn-chat", "tab-chat"],
    ["tab-btn-metrics", "tab-metrics"],
  ];
  tabs.forEach(([btnId, panelId]) => {
    const btn = document.getElementById(btnId);
    btn.onclick = () => {
      tabs.forEach(([b2, p2]) => {
        document.getElementById(b2).setAttribute("aria-selected", b2 === btnId ? "true" : "false");
        document.getElementById(p2).hidden = (p2 !== panelId);
      });
    };
  });
}

function renderCaseList() {
  const ul = document.getElementById("case-list");
  ul.innerHTML = "";
  currentInvestigation.cases.forEach((c, idx) => {
    const li = document.createElement("li");
    const cat = c.causality ? c.causality.category : "Unassessable";
    const failed = c.extraction.extraction_failed;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "case-item-btn";
    btn.setAttribute("aria-current", idx === currentCaseIndex ? "true" : "false");
    btn.innerHTML = `
      <span class="case-id">${esc(c.report.report_id)}</span>
      <span>${categoryBadge(cat)} ${failed ? '<span class="badge badge-danger">&#9888; extraction failed</span>' : ""}</span>
    `;
    btn.addEventListener("click", () => { currentCaseIndex = idx; renderCaseList(); renderCaseDetail(); });
    li.appendChild(btn);
    ul.appendChild(li);
  });
}

const FACT_LABELS = {
  time_to_onset_days: "Time to onset",
  onset_order: "Onset order",
  dechallenge: "Dechallenge",
  rechallenge: "Rechallenge",
  confounder: "Confounder",
};

function renderCaseDetail() {
  const container = document.getElementById("case-detail");
  const c = currentInvestigation.cases[currentCaseIndex];
  if (!c) { container.innerHTML = `<p class="hint">No case selected.</p>`; return; }

  const report = c.report;
  const ext = c.extraction;
  const causality = c.causality;

  let failureNotice = "";
  if (ext.extraction_failed) {
    failureNotice = `<p class="fact-unverified-note">&#9888; Extraction failed for this case: ${esc(ext.failure_reason)}. No AI facts are available; causality was marked Unassessable rather than guessed.</p>`;
  }

  const factsHtml = (ext.facts || []).length === 0 ? `<p class="hint">No facts recorded.</p>` : `
    <ul class="facts-list">
      ${ext.facts.map((f, i) => renderFactButton(f, i)).join("")}
    </ul>
  `;

  container.innerHTML = `
    <h3>Case ${esc(report.report_id)}</h3>
    <p class="rule-meta">
      ${esc(report.age)}y ${esc(report.sex)} &middot; ${esc(report.seriousness)} &middot; ${esc(report.country)} &middot; received ${esc(report.received_date)}
      &middot; cache: ${ext.cache_hit ? "hit (reused, no new LLM call)" : "miss (new LLM call)"}
    </p>
    ${failureNotice}

    <h4>Narrative <span class="badge badge-ai">&#129302; source text</span></h4>
    <div class="narrative-box" id="narrative-box" data-report-id="${esc(report.report_id)}">${esc(report.narrative)}</div>

    <h4>Extracted facts <span class="badge badge-ai">&#129302; AI-derived</span> &middot; system-verified quotes are click-navigable</h4>
    ${factsHtml}
    <p class="rule-meta">Quotes verified: ${ext.quotes_verified} &middot; quotes rejected (downgraded to unknown): ${ext.quotes_rejected}</p>

    <h4>Causality ${causality ? sourceBadge(causality.source) : ""}</h4>
    ${causality ? `
      <p>${categoryBadge(causality.category)}</p>
      <p>${esc(causality.explanation)}</p>
      <p class="rule-meta">${causality.source === "override"
        ? `Overridden by ${esc(causality.overridden_by)}: "${esc(causality.override_reason)}"`
        : `Rule ${esc(causality.rule_id)} (ruleset ${esc(causality.ruleset_version)})`}</p>
    ` : `<p class="hint">Not assessed.</p>`}

    <fieldset>
      <legend>Override causality</legend>
      <form id="override-form">
        <label for="override-category">New category</label>
        <select id="override-category" required>
          ${["Certain", "Probable", "Possible", "Unlikely", "Unassessable"].map((cat) =>
            `<option value="${cat}" ${causality && causality.category === cat ? "selected" : ""}>${cat}</option>`).join("")}
        </select>
        <label for="override-reason">Reason (required)</label>
        <textarea id="override-reason" required placeholder="Explain your clinical judgement for this override…"></textarea>
        <label for="override-actor">Your name</label>
        <input type="text" id="override-actor" value="reviewer" required>
        <button type="submit" class="btn">Submit override</button>
      </form>
    </fieldset>
  `;

  document.getElementById("override-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const category = document.getElementById("override-category").value;
    const reason = document.getElementById("override-reason").value;
    const actor = document.getElementById("override-actor").value;
    try {
      const inv = await withBusy("Applying override and recomputing recommendation…", () =>
        apiPost(`/api/investigations/${currentInvestigation.investigation_id}/cases/${report.report_id}/override`, { category, reason, actor })
      );
      renderInvestigation(inv);
    } catch (e) { setError(e.message); }
  });
}

function renderFactButton(fact, i) {
  const label = FACT_LABELS[fact.field] || fact.field;
  const isUnknown = fact.value === null || fact.value === undefined || fact.value === "unknown" || fact.value === "unclear";
  if (isUnknown) {
    return `<li><div class="fact-btn"><span class="fact-label">${esc(label)}:</span> <span class="fact-value fact-unknown">unknown / not documented</span></div></li>`;
  }
  if (fact.verified === false) {
    return `<li><div class="fact-btn">
      <span class="fact-label">${esc(label)}:</span> <span class="fact-value">${esc(fact.value)}</span>
      <div class="fact-unverified-note">&#9888; Quote could not be verified against the narrative &mdash; downgraded to unknown, no highlight shown.</div>
    </div></li>`;
  }
  return `<li><button type="button" class="fact-btn evidence-btn" data-idx="${i}" data-start="${fact.char_start}" data-end="${fact.char_end}">
    <span class="fact-label">${esc(label)}:</span> <span class="fact-value">${esc(fact.value)}</span>
    <span class="evidence-source-tag">&#128269; Verified quote &mdash; click to view in source narrative</span>
  </button></li>`;
}

// Attach evidence-navigation clicks after render (delegated on container each render).
document.getElementById("case-detail").addEventListener("click", (ev) => {
  const btn = ev.target.closest(".evidence-btn");
  if (!btn) return;
  const start = parseInt(btn.dataset.start, 10);
  const end = parseInt(btn.dataset.end, 10);
  const reportId = document.getElementById("narrative-box").dataset.reportId;
  highlightNarrativeSpan(reportId, start, end, FACT_LABELS[Object.keys(FACT_LABELS).find(() => true)] || "fact");
});

function highlightNarrativeSpan(reportId, start, end, label) {
  const box = document.getElementById("narrative-box");
  if (!box || box.dataset.reportId !== reportId) {
    announce(`Evidence is in case ${reportId}, which is not the case currently shown.`);
    return;
  }
  const full = currentInvestigation.cases[currentCaseIndex].report.narrative;
  if (isNaN(start) || isNaN(end) || start < 0 || end > full.length) {
    announce("No verified evidence location available for this fact.");
    return;
  }
  const before = full.slice(0, start);
  const quote = full.slice(start, end);
  const after = full.slice(end);
  box.innerHTML = `${esc(before)}<mark class="evidence-highlight" tabindex="-1">${esc(quote)}</mark>${esc(after)}`;
  const mark = box.querySelector("mark");
  mark.scrollIntoView({ behavior: "smooth", block: "center" });
  mark.focus();
  announce(`Showing verified evidence from case ${reportId}: "${quote}"`);
}

function announce(text) {
  document.getElementById("evidence-announcer").textContent = text;
}

/* ---------- Recommendation ---------- */

function renderRecommendation() {
  const container = document.getElementById("recommendation-card");
  const rec = currentInvestigation.recommendation;
  if (!rec) { container.innerHTML = "<p>No recommendation computed yet.</p>"; return; }

  let cls = "";
  if (rec.recommendation.startsWith("Validated")) cls = "validated";
  else if (rec.recommendation.startsWith("Not confirmed")) cls = "confounded";
  else cls = "insufficient";

  container.innerHTML = `
    <div class="recommendation-card ${cls}">
      <p class="recommendation-title">${esc(rec.recommendation)}</p>
      <p>${esc(rec.explanation)}</p>
      <p class="rule-meta">
        Rule ${esc(rec.rule_id)} &middot; ruleset ${esc(rec.ruleset_version)} &middot;
        thresholds: supportive &ge; ${fmtNum(rec.thresholds.supportive_fraction_threshold, 2)},
        unsupportive &ge; ${fmtNum(rec.thresholds.unsupportive_fraction_threshold, 2)},
        unassessable &ge; ${fmtNum(rec.thresholds.unassessable_fraction_threshold, 2)}
      </p>
      <p class="rule-meta">Causality distribution: ${Object.entries(rec.causality_counts).map(([k, v]) => `${k}: ${v}`).join(", ")}</p>
    </div>
  `;
}

/* ---------- Summary + sign-off ---------- */

function renderSummary() {
  const container = document.getElementById("summary-section");
  const inv = currentInvestigation;
  const signedOff = inv.status === "signed_off";

  container.innerHTML = `
    <div>
      <button type="button" class="btn secondary" id="draft-summary-btn" ${signedOff ? "disabled" : ""}>
        ${inv.summary_draft ? "Regenerate AI draft" : "Generate AI draft"}
      </button>
    </div>
    ${inv.summary_draft ? `
      <div class="ai-label">AI draft &ndash; requires human approval</div>
      <div class="summary-text">${esc(inv.summary_draft)}</div>
    ` : `<p class="hint">No AI draft generated yet.</p>`}

    <h3>Final summary (editable by reviewer)</h3>
    <form id="summary-edit-form">
      <label for="summary-final-text">Edit and finalize the summary text</label>
      <textarea id="summary-final-text" style="min-height:160px" ${signedOff ? "disabled" : ""}>${esc(inv.summary_final || inv.summary_draft || "")}</textarea>
      <button type="submit" class="btn secondary" ${signedOff ? "disabled" : ""}>Save summary</button>
    </form>

    <h3>Sign-off</h3>
    ${signedOff ? `
      <p><span class="badge badge-ok">&#10003; Signed off</span> by ${esc(inv.signed_off_by)} on ${esc((inv.signed_off_at || "").slice(0, 19).replace("T", " "))}</p>
      <p>Decision: ${esc(inv.final_decision)}${inv.decision_reason ? ` &mdash; ${esc(inv.decision_reason)}` : ""}</p>
    ` : `
      <p class="hint">Sign-off requires a summary to exist. The investigation cannot be marked complete without it.</p>
      <form id="signoff-form">
        <label for="signoff-name">Reviewer name</label>
        <input type="text" id="signoff-name" required>
        <label for="signoff-decision">Decision</label>
        <select id="signoff-decision">
          <option value="accept_recommendation">Accept the computed recommendation</option>
          <option value="override_recommendation">Override the recommendation</option>
        </select>
        <label for="signoff-reason">Reason (required if overriding)</label>
        <textarea id="signoff-reason"></textarea>
        <button type="submit" class="btn">Sign off</button>
      </form>
    `}
  `;

  const draftBtn = document.getElementById("draft-summary-btn");
  if (draftBtn) draftBtn.addEventListener("click", async () => {
    try {
      const inv2 = await withBusy("Generating AI draft summary…", () =>
        apiPost(`/api/investigations/${inv.investigation_id}/summary/draft`, {}));
      renderInvestigation(inv2);
    } catch (e) { setError(e.message); }
  });

  const editForm = document.getElementById("summary-edit-form");
  if (editForm) editForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const text = document.getElementById("summary-final-text").value;
    try {
      const inv2 = await withBusy("Saving summary…", () =>
        apiPut(`/api/investigations/${inv.investigation_id}/summary`, { text, actor: "reviewer" }));
      renderInvestigation(inv2);
    } catch (e) { setError(e.message); }
  });

  const signoffForm = document.getElementById("signoff-form");
  if (signoffForm) signoffForm.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const actor_name = document.getElementById("signoff-name").value;
    const final_decision = document.getElementById("signoff-decision").value;
    const decision_reason = document.getElementById("signoff-reason").value;
    try {
      const inv2 = await withBusy("Recording sign-off…", () =>
        apiPost(`/api/investigations/${inv.investigation_id}/signoff`, { actor_name, final_decision, decision_reason }));
      renderInvestigation(inv2);
    } catch (e) { setError(e.message); }
  });
}

/* ---------- Metrics ---------- */

async function renderMetrics() {
  const container = document.getElementById("metrics-panel");
  try {
    const m = await apiGet(`/api/investigations/${currentInvestigation.investigation_id}/metrics`);
    container.innerHTML = `
      <div class="metrics-grid">
        ${tile(m.cases_processed, "Cases processed")}
        ${tile(fmtNum(m.ai_processing_seconds, 1) + "s", "AI processing time")}
        ${tile(m.facts_extracted, "Facts extracted")}
        ${tile(m.quotes_verified, "Quotes verified")}
        ${tile(m.quotes_rejected, "Quotes rejected")}
        ${tile(m.extraction_failures, "Extraction failures")}
        ${tile(fmtNum(m.estimated_manual_hours_saved, 1) + "h", "Est. manual time saved")}
      </div>
      <p class="hint">Assumption: ${m.manual_minutes_per_case_assumption} minutes of manual review per case (configurable via MANUAL_MINUTES_PER_CASE).</p>
    `;
  } catch (e) {
    container.innerHTML = `<p>Failed to load metrics: ${esc(e.message)}</p>`;
  }
}
function tile(value, label) {
  return `<div class="metric-tile"><div class="metric-value">${esc(value)}</div><div class="metric-label">${esc(label)}</div></div>`;
}

/* ---------- Chatbot ---------- */

async function loadChatHistory(investigationId) {
  try {
    const { messages } = await apiGet(`/api/investigations/${investigationId}/chat`);
    renderChatHistory(messages);
  } catch (e) { /* non-fatal */ }
}

function renderChatHistory(messages) {
  const log = document.getElementById("chat-log");
  log.innerHTML = "";
  messages.forEach((m) => appendChatExchange(m.question, { answer: m.answer, citations: m.citations }));
}

function appendChatExchange(question, result) {
  const log = document.getElementById("chat-log");
  const userDiv = document.createElement("div");
  userDiv.className = "chat-msg user";
  userDiv.innerHTML = `<strong>You:</strong> ${esc(question)}`;
  log.appendChild(userDiv);

  const botDiv = document.createElement("div");
  botDiv.className = "chat-msg assistant";
  const citationsHtml = (result.citations || []).map((c) => {
    if (c.verified) {
      return `<button type="button" class="citation-chip evidence-btn" data-idx="0" data-start="${c.char_start}" data-end="${c.char_end}" data-report="${esc(c.case_id)}">${esc(c.case_id)}</button>`;
    }
    return `<span class="citation-chip unverified">${esc(c.case_id)} &ndash; unverified</span>`;
  }).join("");
  botDiv.innerHTML = `
    <strong>Copilot:</strong> ${esc(result.answer)}
    ${result.error ? `<p class="fact-unverified-note">&#9888; ${esc(result.error)}</p>` : ""}
    <div>${citationsHtml}</div>
  `;
  log.appendChild(botDiv);
  botDiv.querySelectorAll(".citation-chip.evidence-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const reportId = btn.dataset.report;
      // Switch to that case in the Cases tab if possible, then highlight.
      const idx = currentInvestigation.cases.findIndex((c) => c.report.report_id === reportId);
      document.getElementById("tab-btn-cases").click();
      if (idx >= 0) {
        currentCaseIndex = idx;
        renderCaseList();
        renderCaseDetail();
        const start = parseInt(btn.dataset.start, 10);
        const end = parseInt(btn.dataset.end, 10);
        if (!isNaN(start) && !isNaN(end)) {
          setTimeout(() => highlightNarrativeSpan(reportId, start, end), 0);
        } else {
          announce(`Jumped to case ${reportId} (evidence is a case-level summary without a specific narrative span).`);
        }
      }
    });
  });
  log.scrollTop = log.scrollHeight;
}

document.getElementById("chat-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const input = document.getElementById("chat-input");
  const question = input.value.trim();
  if (!question) return;
  input.value = "";
  try {
    const result = await withBusy("Retrieving evidence and asking the model…", () =>
      apiPost(`/api/investigations/${currentInvestigation.investigation_id}/chat`, { question, actor: "reviewer" }));
    appendChatExchange(question, result);
  } catch (e) { setError(e.message); }
});

/* ================= AUDIT VIEW ================= */

async function loadAudit() {
  const tbody = document.getElementById("audit-tbody");
  tbody.innerHTML = `<tr><td colspan="7">Loading…</td></tr>`;
  try {
    const { events } = await apiGet("/api/audit");
    tbody.innerHTML = "";
    events.slice().reverse().forEach((e) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${e.seq}</td>
        <td>${esc((e.timestamp || "").slice(0, 19).replace("T", " "))}</td>
        <td>${esc(e.event_type)}</td>
        <td>${esc(e.investigation_id || "—")}</td>
        <td>${esc(e.actor || "—")}</td>
        <td>${esc(e.model_id || e.rule_version || "—")}</td>
        <td><details><summary>view</summary><pre class="overflow-x">${esc(JSON.stringify(e.payload, null, 2))}</pre></details></td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="7">Failed to load audit log: ${esc(e.message)}</td></tr>`;
  }
}

document.getElementById("verify-chain-btn").addEventListener("click", async () => {
  const out = document.getElementById("chain-status");
  try {
    const result = await withBusy("Verifying hash chain…", () => apiGet("/api/audit/verify"));
    out.innerHTML = result.valid
      ? `<span class="badge badge-ok">&#10003; Chain valid</span> (${result.events_checked} events checked)`
      : `<span class="badge badge-danger">&#10007; Chain broken at event #${result.broken_at_seq}</span> (${result.reason})`;
  } catch (e) { setError(e.message); }
});

/* ---------- Init ---------- */

loadDashboard();
