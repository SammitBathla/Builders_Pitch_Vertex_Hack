import React, { useEffect, useState } from "react";
import { apiGet, apiPost } from "../api.js";
import { useApp } from "../AppContext.jsx";
import { fmtNum, fmtDate } from "../format.js";
import { StatusBadge } from "./Badges.jsx";
import TableDialog from "./TableDialog.jsx";

export default function Dashboard({ onOpenInvestigation }) {
  const { withBusy, setError } = useApp();
  const [signals, setSignals] = useState(null);
  const [investigations, setInvestigations] = useState(null);
  const [tableData, setTableData] = useState(null);

  async function loadAll() {
    try {
      const [{ signals: s }, { investigations: inv }] = await withBusy("Loading dashboard…", () =>
        Promise.all([apiGet("/api/signals"), apiGet("/api/investigations")])
      );
      setSignals(s);
      setInvestigations(inv);
    } catch (e) {
      setSignals([]);
      setInvestigations([]);
    }
  }

  useEffect(() => {
    loadAll();
  }, []);

  async function showTable(drug, event) {
    try {
      const s = await withBusy("Loading 2×2 table…", () =>
        apiGet(`/api/signals/table?drug=${encodeURIComponent(drug)}&event=${encodeURIComponent(event)}`)
      );
      setTableData(s);
    } catch (e) {
      /* status already shows the error */
    }
  }

  async function investigate(drug, event) {
    try {
      const inv = await withBusy(
        `Running extraction + guardrails + causality rules for ${drug} / ${event}… this calls the LLM for every case and can take a little while.`,
        () => apiPost("/api/investigations", { drug, event, actor: "reviewer" })
      );
      onOpenInvestigation(inv);
    } catch (e) {
      /* status already shows the error */
    }
  }

  async function openExisting(id) {
    try {
      const inv = await withBusy("Loading investigation…", () => apiGet(`/api/investigations/${id}`));
      onOpenInvestigation(inv);
    } catch (e) {
      /* status already shows the error */
    }
  }

  return (
    <section className="view">
      <h1>Flagged Signals</h1>
      <p className="hint">
        Drug&ndash;event pairs meeting the Evans disproportionality criteria (PRR &ge; 2, chi-square &ge; 4, case
        count &ge; 3), ranked by PRR.
      </p>

      <div className="overflow-x">
        <table className="data-table">
          <caption className="sr-only">Flagged signals ranked by PRR</caption>
          <thead>
            <tr>
              <th scope="col">Drug</th>
              <th scope="col">Event</th>
              <th scope="col">Cases (a)</th>
              <th scope="col">PRR</th>
              <th scope="col">ROR (95% CI)</th>
              <th scope="col">&chi;&sup2;</th>
              <th scope="col">2&times;2 table</th>
              <th scope="col">Investigation</th>
            </tr>
          </thead>
          <tbody>
            {signals === null && (
              <tr><td colSpan={8}>Loading signals&hellip;</td></tr>
            )}
            {signals !== null && signals.length === 0 && (
              <tr><td colSpan={8}>No flagged signals found.</td></tr>
            )}
            {signals?.map((s) => (
              <tr key={`${s.drug}|${s.event}`}>
                <td>{s.drug}</td>
                <td>{s.event}</td>
                <td>{s.a}</td>
                <td>{fmtNum(s.prr)}</td>
                <td>{s.ror !== null ? `${fmtNum(s.ror)} (${fmtNum(s.ror_ci_low)}–${fmtNum(s.ror_ci_high)})` : "—"}</td>
                <td>{fmtNum(s.chi_square)}</td>
                <td>
                  <button type="button" className="link-button" onClick={() => showTable(s.drug, s.event)}>
                    2&times;2 table
                  </button>
                </td>
                <td>
                  <button type="button" className="btn" onClick={() => investigate(s.drug, s.event)}>
                    Investigate
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Investigations</h2>
      {investigations === null && <p className="hint">Loading&hellip;</p>}
      {investigations !== null && investigations.length === 0 && (
        <p className="hint">No investigations started yet &mdash; click "Investigate" on a signal above.</p>
      )}
      {investigations !== null && investigations.length > 0 && (
        <div className="overflow-x">
          <table className="data-table">
            <caption className="sr-only">Existing investigations</caption>
            <thead>
              <tr>
                <th scope="col">Drug</th>
                <th scope="col">Event</th>
                <th scope="col">Status</th>
                <th scope="col">Recommendation</th>
                <th scope="col">Created</th>
                <th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {investigations.map((inv) => (
                <tr key={inv.investigation_id}>
                  <td>{inv.drug}</td>
                  <td>{inv.event}</td>
                  <td><StatusBadge status={inv.status} /></td>
                  <td>{inv.recommendation || "—"}</td>
                  <td>{fmtDate(inv.created_at)}</td>
                  <td>
                    <button type="button" className="btn secondary" onClick={() => openExisting(inv.investigation_id)}>
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <TableDialog data={tableData} onClose={() => setTableData(null)} />
    </section>
  );
}
