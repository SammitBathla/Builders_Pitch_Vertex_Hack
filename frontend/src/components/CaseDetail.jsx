import React, { useEffect, useRef, useState } from "react";
import { apiPost } from "../api.js";
import { useApp } from "../AppContext.jsx";
import { CategoryBadge, SourceBadge } from "./Badges.jsx";

const FACT_LABELS = {
  time_to_onset_days: "Time to onset",
  onset_order: "Onset order",
  dechallenge: "Dechallenge",
  rechallenge: "Rechallenge",
  confounder: "Confounder",
};

const CAUSALITY_CATEGORIES = ["Certain", "Probable", "Possible", "Unlikely", "Unassessable"];

export default function CaseDetail({ caseData, investigation, setInvestigation, highlightRequest }) {
  const { announce, withBusy, setError } = useApp();
  const { report, extraction, causality } = caseData;
  const [highlight, setHighlight] = useState(null); // {start, end}
  const markRef = useRef(null);

  const [category, setCategory] = useState(causality ? causality.category : "Unassessable");
  const [reason, setReason] = useState("");
  const [actor, setActor] = useState("reviewer");

  // Reset local override form + clear any stale highlight when the selected case changes
  // (the `key` on this component in CasesTab already remounts it per case, but keep this
  // for cross-tab navigation onto a case that's already mounted).
  useEffect(() => {
    setCategory(causality ? causality.category : "Unassessable");
  }, [report.report_id, causality]);

  // Cross-tab evidence navigation (e.g. clicking a chat citation).
  useEffect(() => {
    if (!highlightRequest || highlightRequest.reportId !== report.report_id) return;
    const { start, end } = highlightRequest;
    if (start == null || end == null || isNaN(start) || isNaN(end)) {
      announce("No verified evidence location available for this fact.");
      return;
    }
    setHighlight({ start, end });
  }, [highlightRequest]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (highlight && markRef.current) {
      markRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
      markRef.current.focus();
      const quote = report.narrative.slice(highlight.start, highlight.end);
      announce(`Showing verified evidence from case ${report.report_id}: "${quote}"`);
    }
  }, [highlight]); // eslint-disable-line react-hooks/exhaustive-deps

  function renderNarrative() {
    const full = report.narrative;
    if (!highlight) return full;
    const { start, end } = highlight;
    if (start < 0 || end > full.length) return full;
    return (
      <>
        {full.slice(0, start)}
        <mark className="evidence-highlight" tabIndex={-1} ref={markRef}>
          {full.slice(start, end)}
        </mark>
        {full.slice(end)}
      </>
    );
  }

  async function submitOverride(ev) {
    ev.preventDefault();
    try {
      const updated = await withBusy("Applying override and recomputing recommendation…", () =>
        apiPost(`/api/investigations/${investigation.investigation_id}/cases/${report.report_id}/override`, {
          category,
          reason,
          actor,
        })
      );
      setInvestigation(updated);
    } catch (e) {
      /* status already shows the error */
    }
  }

  const facts = extraction.facts || [];

  return (
    <div>
      <h3>Case {report.report_id}</h3>
      <p className="rule-meta">
        {report.age}y {report.sex} &middot; {report.seriousness} &middot; {report.country} &middot; received {report.received_date}
        &middot; cache: {extraction.cache_hit ? "hit (reused, no new LLM call)" : "miss (new LLM call)"}
      </p>

      {extraction.extraction_failed && (
        <p className="fact-unverified-note">
          {"⚠"} Extraction failed for this case: {extraction.failure_reason}. No AI facts are available;
          causality was marked Unassessable rather than guessed.
        </p>
      )}

      <h4>Narrative <span className="badge badge-ai">{"🤖"} source text</span></h4>
      <div className="narrative-box">{renderNarrative()}</div>

      <h4>
        Extracted facts <span className="badge badge-ai">{"🤖"} AI-derived</span> &middot; system-verified
        quotes are click-navigable
      </h4>
      {facts.length === 0 ? (
        <p className="hint">No facts recorded.</p>
      ) : (
        <ul className="facts-list">
          {facts.map((f, i) => {
            const label = FACT_LABELS[f.field] || f.field;
            const isUnknown = f.value === null || f.value === undefined || f.value === "unknown" || f.value === "unclear";
            if (isUnknown) {
              return (
                <li key={i}>
                  <div className="fact-btn">
                    <span className="fact-label">{label}:</span>{" "}
                    <span className="fact-value fact-unknown">unknown / not documented</span>
                  </div>
                </li>
              );
            }
            if (f.verified === false) {
              return (
                <li key={i}>
                  <div className="fact-btn">
                    <span className="fact-label">{label}:</span> <span className="fact-value">{String(f.value)}</span>
                    <div className="fact-unverified-note">
                      {"⚠"} Quote could not be verified against the narrative &mdash; downgraded to unknown, no
                      highlight shown.
                    </div>
                  </div>
                </li>
              );
            }
            return (
              <li key={i}>
                <button
                  type="button"
                  className="fact-btn evidence-btn"
                  onClick={() => setHighlight({ start: f.char_start, end: f.char_end })}
                >
                  <span className="fact-label">{label}:</span> <span className="fact-value">{String(f.value)}</span>
                  <span className="evidence-source-tag">{"🔍"} Verified quote &mdash; click to view in source narrative</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="rule-meta">
        Quotes verified: {extraction.quotes_verified} &middot; quotes rejected (downgraded to unknown): {extraction.quotes_rejected}
      </p>

      <h4>Causality {causality && <SourceBadge source={causality.source} />}</h4>
      {causality ? (
        <>
          <p><CategoryBadge category={causality.category} /></p>
          <p>{causality.explanation}</p>
          <p className="rule-meta">
            {causality.source === "override"
              ? `Overridden by ${causality.overridden_by}: "${causality.override_reason}"`
              : `Rule ${causality.rule_id} (ruleset ${causality.ruleset_version})`}
          </p>
        </>
      ) : (
        <p className="hint">Not assessed.</p>
      )}

      <fieldset>
        <legend>Override causality</legend>
        <form onSubmit={submitOverride}>
          <label htmlFor="override-category">New category</label>
          <select id="override-category" value={category} onChange={(e) => setCategory(e.target.value)} required>
            {CAUSALITY_CATEGORIES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <label htmlFor="override-reason">Reason (required)</label>
          <textarea
            id="override-reason"
            required
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Explain your clinical judgement for this override…"
          />
          <label htmlFor="override-actor">Your name</label>
          <input id="override-actor" type="text" required value={actor} onChange={(e) => setActor(e.target.value)} />
          <button type="submit" className="btn">Submit override</button>
        </form>
      </fieldset>
    </div>
  );
}
