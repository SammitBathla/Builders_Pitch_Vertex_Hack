import React, { useEffect, useState } from "react";
import { apiGet } from "../api.js";
import { useApp } from "../AppContext.jsx";
import { fmtDate } from "../format.js";

function EventRow({ e }) {
  const [open, setOpen] = useState(false);
  return (
    <tr>
      <td>{e.seq}</td>
      <td>{fmtDate(e.timestamp)}</td>
      <td>{e.event_type}</td>
      <td>{e.investigation_id || "—"}</td>
      <td>{e.actor || "—"}</td>
      <td>{e.model_id || e.rule_version || "—"}</td>
      <td>
        <button type="button" className="link-button" onClick={() => setOpen((o) => !o)}>
          {open ? "hide" : "view"}
        </button>
        {open && <pre className="overflow-x">{JSON.stringify(e.payload, null, 2)}</pre>}
      </td>
    </tr>
  );
}

export default function AuditView() {
  const { withBusy } = useApp();
  const [events, setEvents] = useState(null);
  const [chainStatus, setChainStatus] = useState(null);

  useEffect(() => {
    apiGet("/api/audit")
      .then((d) => setEvents(d.events.slice().reverse()))
      .catch(() => setEvents([]));
  }, []);

  async function verify() {
    try {
      const result = await withBusy("Verifying hash chain…", () => apiGet("/api/audit/verify"));
      setChainStatus(result);
    } catch (e) {
      /* status shows error */
    }
  }

  return (
    <section className="view">
      <h1>Audit Trail</h1>
      <p className="hint">
        Every AI call, rule evaluation, override and sign-off, hash-chained so tampering is detectable.
      </p>
      <button type="button" onClick={verify}>Verify chain integrity</button>
      <div role="status" aria-live="polite">
        {chainStatus &&
          (chainStatus.valid ? (
            <span className="badge badge-ok">{"✓"} Chain valid</span>
          ) : (
            <span className="badge badge-danger">{"✗"} Chain broken at event #{chainStatus.broken_at_seq}</span>
          ))}
        {chainStatus && ` (${chainStatus.events_checked} events checked)`}
      </div>
      <div className="overflow-x">
        <table className="data-table">
          <caption className="sr-only">Audit log events</caption>
          <thead>
            <tr>
              <th scope="col">#</th>
              <th scope="col">Time (UTC)</th>
              <th scope="col">Event</th>
              <th scope="col">Investigation</th>
              <th scope="col">Actor</th>
              <th scope="col">Model / Rule version</th>
              <th scope="col">Details</th>
            </tr>
          </thead>
          <tbody>
            {events === null && <tr><td colSpan={7}>Loading&hellip;</td></tr>}
            {events?.map((e) => <EventRow key={e.seq} e={e} />)}
          </tbody>
        </table>
      </div>
    </section>
  );
}
