import React, { useEffect, useRef, useState } from "react";
import { apiGet } from "../api.js";

export default function AssumptionsDialog({ open, onClose }) {
  const ref = useRef(null);
  const [assumptions, setAssumptions] = useState([]);

  useEffect(() => {
    if (!open) return;
    apiGet("/api/config")
      .then((cfg) => setAssumptions(cfg.assumptions || []))
      .catch((e) => setAssumptions([`Failed to load: ${e.message}`]));
  }, [open]);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog ref={ref} onClose={onClose}>
      <h2>Stated Assumptions</h2>
      <ul>
        {assumptions.map((a, i) => (
          <li key={i}>{a}</li>
        ))}
      </ul>
      <button type="button" onClick={onClose}>Close</button>
    </dialog>
  );
}
