import React, { useEffect, useRef } from "react";
import { fmtNum } from "../format.js";

export default function TableDialog({ data, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (data && !dialog.open) dialog.showModal();
    if (!data && dialog.open) dialog.close();
  }, [data]);

  return (
    <dialog ref={ref} onClose={onClose}>
      {data && (
        <>
          <h2>2&times;2 Contingency Table &ndash; {data.drug} / {data.event}</h2>
          <table className="data-table">
            <caption className="sr-only">2 by 2 contingency table for {data.drug} and {data.event}</caption>
            <thead>
              <tr><th scope="col"></th><th scope="col">{data.event}</th><th scope="col">All other events</th></tr>
            </thead>
            <tbody>
              <tr><th scope="row">{data.drug}</th><td>a = {data.a}</td><td>b = {data.b}</td></tr>
              <tr><th scope="row">All other drugs</th><td>c = {data.c}</td><td>d = {data.d}</td></tr>
            </tbody>
          </table>
          <p>
            PRR: <strong>{fmtNum(data.prr)}</strong> &middot; ROR: <strong>{fmtNum(data.ror)}</strong>{" "}
            (95% CI {fmtNum(data.ror_ci_low)}&ndash;{fmtNum(data.ror_ci_high)}) &middot; &chi;&sup2;:{" "}
            <strong>{fmtNum(data.chi_square)}</strong>
          </p>
          <p>
            {data.is_signal ? (
              <span className="badge badge-ok">&#10003; Meets Evans signal criteria</span>
            ) : (
              <span className="badge badge-unknown">Does not meet Evans signal criteria</span>
            )}
          </p>
        </>
      )}
      <button type="button" onClick={onClose}>Close</button>
    </dialog>
  );
}
