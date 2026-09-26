import React, { useEffect, useState } from "react";
import { apiGet } from "../api.js";
import { fmtNum } from "../format.js";

function Tile({ value, label }) {
  return (
    <div className="metric-tile">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
    </div>
  );
}

export default function MetricsTab({ investigation }) {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiGet(`/api/investigations/${investigation.investigation_id}/metrics`)
      .then(setMetrics)
      .catch((e) => setError(e.message));
  }, [investigation.investigation_id]);

  return (
    <div>
      <h2>Effort-Reduction Metrics</h2>
      {error && <p>Failed to load metrics: {error}</p>}
      {!error && !metrics && <p className="hint">Loading&hellip;</p>}
      {metrics && (
        <>
          <div className="metrics-grid">
            <Tile value={metrics.cases_processed} label="Cases processed" />
            <Tile value={`${fmtNum(metrics.ai_processing_seconds, 1)}s`} label="AI processing time" />
            <Tile value={metrics.facts_extracted} label="Facts extracted" />
            <Tile value={metrics.quotes_verified} label="Quotes verified" />
            <Tile value={metrics.quotes_rejected} label="Quotes rejected" />
            <Tile value={metrics.extraction_failures} label="Extraction failures" />
            <Tile value={`${fmtNum(metrics.estimated_manual_hours_saved, 1)}h`} label="Est. manual time saved" />
          </div>
          <p className="hint">
            Assumption: {metrics.manual_minutes_per_case_assumption} minutes of manual review per case (configurable
            via MANUAL_MINUTES_PER_CASE).
          </p>
        </>
      )}
    </div>
  );
}
