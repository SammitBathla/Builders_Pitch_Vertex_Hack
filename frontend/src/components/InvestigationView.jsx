import React, { useState } from "react";
import { fmtNum } from "../format.js";
import { StatusBadge } from "./Badges.jsx";
import CasesTab from "./CasesTab.jsx";
import SummaryTab from "./SummaryTab.jsx";
import ChatTab from "./ChatTab.jsx";
import MetricsTab from "./MetricsTab.jsx";

const TABS = [
  { id: "cases", label: "Cases & Evidence" },
  { id: "summary", label: "Recommendation & Summary" },
  { id: "chat", label: "Ask the Copilot" },
  { id: "metrics", label: "Effort Metrics" },
];

export default function InvestigationView({ investigation, setInvestigation, onBack }) {
  const [activeTab, setActiveTab] = useState("cases");
  const [currentCaseIndex, setCurrentCaseIndex] = useState(0);
  const [highlightRequest, setHighlightRequest] = useState(null);

  const inv = investigation;
  const st = inv.stats;

  function navigateToEvidence(reportId, start, end) {
    const idx = inv.cases.findIndex((c) => c.report.report_id === reportId);
    setActiveTab("cases");
    if (idx >= 0) {
      setCurrentCaseIndex(idx);
      setHighlightRequest({ reportId, start, end, nonce: Date.now() });
    }
  }

  return (
    <section className="view">
      <button type="button" className="link-button" onClick={onBack}>&larr; Back to dashboard</button>

      <h1>{inv.drug} &ndash; {inv.event}</h1>
      <p className="rule-meta">
        Investigation {inv.investigation_id} &middot; <StatusBadge status={inv.status} signedOffBy={inv.signed_off_by} />
        &middot; Cases: {st.a} &middot; PRR {fmtNum(st.prr)} &middot; &chi;&sup2; {fmtNum(st.chi_square)}
        &middot; AI processing time: {fmtNum(inv.ai_processing_seconds, 1)}s
      </p>

      <div className="tabs" role="tablist" aria-label="Investigation sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className="tab"
            role="tab"
            aria-selected={activeTab === t.id}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div hidden={activeTab !== "cases"} role="tabpanel">
        <CasesTab
          investigation={inv}
          setInvestigation={setInvestigation}
          currentCaseIndex={currentCaseIndex}
          setCurrentCaseIndex={setCurrentCaseIndex}
          highlightRequest={highlightRequest}
        />
      </div>
      <div hidden={activeTab !== "summary"} role="tabpanel">
        <SummaryTab investigation={inv} setInvestigation={setInvestigation} />
      </div>
      <div hidden={activeTab !== "chat"} role="tabpanel">
        <ChatTab investigation={inv} onNavigateToEvidence={navigateToEvidence} />
      </div>
      <div hidden={activeTab !== "metrics"} role="tabpanel">
        <MetricsTab investigation={inv} />
      </div>
    </section>
  );
}
