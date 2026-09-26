import React from "react";
import { CategoryBadge } from "./Badges.jsx";
import CaseDetail from "./CaseDetail.jsx";

export default function CasesTab({ investigation, setInvestigation, currentCaseIndex, setCurrentCaseIndex, highlightRequest }) {
  const cases = investigation.cases;
  const current = cases[currentCaseIndex];

  return (
    <div className="cases-layout">
      <div className="cases-list-col">
        <h2>Cases</h2>
        <ul className="case-list">
          {cases.map((c, idx) => {
            const cat = c.causality ? c.causality.category : "Unassessable";
            const failed = c.extraction.extraction_failed;
            return (
              <li key={c.report.report_id}>
                <button
                  type="button"
                  className="case-item-btn"
                  aria-current={idx === currentCaseIndex ? "true" : "false"}
                  onClick={() => setCurrentCaseIndex(idx)}
                >
                  <span className="case-id">{c.report.report_id}</span>
                  <span>
                    <CategoryBadge category={cat} />{" "}
                    {failed && <span className="badge badge-danger">{"⚠"} extraction failed</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="case-detail-col">
        <h2>Case Detail</h2>
        {current ? (
          <CaseDetail
            key={current.report.report_id}
            caseData={current}
            investigation={investigation}
            setInvestigation={setInvestigation}
            highlightRequest={highlightRequest}
          />
        ) : (
          <p className="hint">Select a case from the list to view its narrative, extracted facts and causality assessment.</p>
        )}
      </div>
    </div>
  );
}
