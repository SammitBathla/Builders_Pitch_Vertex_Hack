import React, { createContext, useCallback, useContext, useState } from "react";

const AppCtx = createContext(null);

export function AppProvider({ children }) {
  const [status, setStatus] = useState({ text: "", kind: "" });
  const [announceText, setAnnounceText] = useState("");

  const setBusy = useCallback((text) => setStatus({ text, kind: "busy" }), []);
  const setError = useCallback((text) => setStatus({ text, kind: "error" }), []);
  const clearStatus = useCallback(() => setStatus({ text: "", kind: "" }), []);

  const withBusy = useCallback(
    async (text, fn) => {
      setBusy(text);
      try {
        const result = await fn();
        clearStatus();
        return result;
      } catch (e) {
        setError(e.message || String(e));
        throw e;
      }
    },
    [setBusy, setError, clearStatus]
  );

  const announce = useCallback((text) => setAnnounceText(text), []);

  const value = { status, setBusy, setError, clearStatus, withBusy, announce, announceText };
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const ctx = useContext(AppCtx);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
