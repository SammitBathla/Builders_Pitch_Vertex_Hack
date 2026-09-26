import React, { useEffect, useState } from "react";
import { AppProvider, useApp } from "./AppContext.jsx";
import { apiGet } from "./api.js";
import Dashboard from "./components/Dashboard.jsx";
import InvestigationView from "./components/InvestigationView.jsx";
import AuditView from "./components/AuditView.jsx";
import AssumptionsDialog from "./components/AssumptionsDialog.jsx";

function Shell() {
  const [route, setRoute] = useState("dashboard");
  const [investigation, setInvestigation] = useState(null);
  const [assumptionsOpen, setAssumptionsOpen] = useState(false);
  const { status, announceText } = useApp();

  function openInvestigation(inv) {
    setInvestigation(inv);
    setRoute("investigation");
  }

  function goToDashboard() {
    setRoute("dashboard");
  }

  return (
    <>
      <a className="skip-link" href="#main-content">Skip to main content</a>

      <header className="app-header">
        <div className="brand">
          <span className="brand-icon" aria-hidden="true">&#128171;</span>
          <span className="brand-name">AI Signal Investigation Copilot</span>
        </div>
        <nav className="app-nav" aria-label="Primary">
          <button type="button" className="nav-link" aria-current={route === "dashboard" ? "page" : undefined} onClick={goToDashboard}>
            Dashboard
          </button>
          <button type="button" className="nav-link" aria-current={route === "audit" ? "page" : undefined} onClick={() => setRoute("audit")}>
            Audit Trail
          </button>
          <button type="button" className="nav-link" onClick={() => setAssumptionsOpen(true)}>
            Assumptions
          </button>
        </nav>
      </header>

      <div id="status-bar" className={"status-bar" + (status.kind ? " " + status.kind : "")} role="status" aria-live="polite">
        {status.text}
      </div>

      <main id="main-content">
        {route === "dashboard" && <Dashboard onOpenInvestigation={openInvestigation} />}
        {route === "investigation" && investigation && (
          <InvestigationView investigation={investigation} setInvestigation={setInvestigation} onBack={goToDashboard} />
        )}
        {route === "audit" && <AuditView />}
      </main>

      <div className="sr-only" role="status" aria-live="assertive">{announceText}</div>

      <AssumptionsDialog open={assumptionsOpen} onClose={() => setAssumptionsOpen(false)} />
    </>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
