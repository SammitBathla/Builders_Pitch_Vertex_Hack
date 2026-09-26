import React, { useState } from "react";
import { apiPost, apiPut } from "../api.js";
import { useApp } from "../AppContext.jsx";
import { fmtNum, fmtDate } from "../format.js";
import { StatusBadge } from "./Badges.jsx";

function recommendationClass(text) {
  if (text.startsWith("Validated")) return "validated";
  if (text.startsWith("Not confirmed")) return "confounded";
  return "insufficient";
}

export default function SummaryTab({ investigation, setInvestigation }) {
  const { withBusy } = useApp();
  const inv = investigation;
  const rec = inv.recommendation;
  const signedOff = inv.status === "signed_off";

  const [summaryText, setSummaryText] = useState(inv.summary_final || inv.summary_draft || "");
  const [signoffName, setSignoffName] = useState("");
  const [signoffDecision, setSignoffDecision] = useState("accept_recommendation");
  const [signoffReason, setSignoffReason] = useState("");

  async function draftSummary() {
    try {
      const updated = await withBusy("Generating AI draft summary…", () =>
        apiPost(`/api/investigations/${inv.investigation_id}/summary/draft`, {})
      );
      setInvestigation(updated);
      setSummaryText(updated.summary_final || updated.summary_draft || "");
    } catch (e) {
      /* status shows error */
    }
  }

  async function saveSummary(ev) {
    ev.preventDefault();
    try {
      const updated = await withBusy("Saving summary…", () =>
        apiPut(`/api/investigations/${inv.investigation_id}/summary`, { text: summaryText, actor: "reviewer" })
      );
      setInvestigation(updated);
    } catch (e) {
      /* status shows error */
    }
  }

  async function signOff(ev) {
    ev.preventDefault();
    try {
      const updated = await withBusy("Recording sign-off…", () =>
        apiPost(`/api/investigations/${inv.investigation_id}/signoff`, {
          actor_name: signoffName,
          final_decision: signoffDecision,
          decision_reason: signoffReason,
        })
      );
      setInvestigation(updated);
    } catch (e) {
      /* status shows error */
    }
  }

  return (
    <div>
      {rec ? (
        <div className={`recommendation-card ${recommendationClass(rec.recommendation)}`}>
          <p className="recommendation-title">{rec.recommendation}</p>
          <p>{rec.explanation}</p>
          <p className="rule-meta">
            Rule {rec.rule_id} &middot; ruleset {rec.ruleset_version} &middot; thresholds: supportive &ge;{" "}
            {fmtNum(rec.thresholds.supportive_fraction_threshold, 2)}, unsupportive &ge;{" "}
            {fmtNum(rec.thresholds.unsupportive_fraction_threshold, 2)}, unassessable &ge;{" "}
            {fmtNum(rec.thresholds.unassessable_fraction_threshold, 2)}
          </p>
          <p className="rule-meta">
            Causality distribution: {Object.entries(rec.causality_counts).map(([k, v]) => `${k}: ${v}`).join(", ")}
          </p>
        </div>
      ) : (
        <p>No recommendation computed yet.</p>
      )}

      <h2>Investigation Summary</h2>

      <div>
        <button type="button" className="btn secondary" disabled={signedOff} onClick={draftSummary}>
          {inv.summary_draft ? "Regenerate AI draft" : "Generate AI draft"}
        </button>
      </div>

      {inv.summary_draft ? (
        <>
          <div className="ai-label">AI draft &ndash; requires human approval</div>
          <div className="summary-text">{inv.summary_draft}</div>
        </>
      ) : (
        <p className="hint">No AI draft generated yet.</p>
      )}

      <h3>Final summary (editable by reviewer)</h3>
      <form onSubmit={saveSummary}>
        <label htmlFor="summary-final-text">Edit and finalize the summary text</label>
        <textarea
          id="summary-final-text"
          style={{ minHeight: 160 }}
          disabled={signedOff}
          value={summaryText}
          onChange={(e) => setSummaryText(e.target.value)}
        />
        <button type="submit" className="btn secondary" disabled={signedOff}>Save summary</button>
      </form>

      <h3>Sign-off</h3>
      {signedOff ? (
        <>
          <p>
            <StatusBadge status="signed_off" signedOffBy={inv.signed_off_by} /> on {fmtDate(inv.signed_off_at)}
          </p>
          <p>
            Decision: {inv.final_decision}
            {inv.decision_reason ? ` — ${inv.decision_reason}` : ""}
          </p>
        </>
      ) : (
        <>
          <p className="hint">
            Sign-off requires a summary to exist. The investigation cannot be marked complete without it.
          </p>
          <form onSubmit={signOff}>
            <label htmlFor="signoff-name">Reviewer name</label>
            <input id="signoff-name" type="text" required value={signoffName} onChange={(e) => setSignoffName(e.target.value)} />
            <label htmlFor="signoff-decision">Decision</label>
            <select id="signoff-decision" value={signoffDecision} onChange={(e) => setSignoffDecision(e.target.value)}>
              <option value="accept_recommendation">Accept the computed recommendation</option>
              <option value="override_recommendation">Override the recommendation</option>
            </select>
            <label htmlFor="signoff-reason">Reason (required if overriding)</label>
            <textarea id="signoff-reason" value={signoffReason} onChange={(e) => setSignoffReason(e.target.value)} />
            <button type="submit" className="btn">Sign off</button>
          </form>
        </>
      )}
    </div>
  );
}
