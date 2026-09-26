import React, { useEffect, useRef, useState } from "react";
import { apiGet, apiPost } from "../api.js";
import { useApp } from "../AppContext.jsx";

export default function ChatTab({ investigation, onNavigateToEvidence }) {
  const { withBusy } = useApp();
  const [messages, setMessages] = useState([]);
  const [question, setQuestion] = useState("");
  const logRef = useRef(null);

  useEffect(() => {
    apiGet(`/api/investigations/${investigation.investigation_id}/chat`)
      .then(({ messages }) => setMessages(messages.map((m) => ({ question: m.question, answer: m.answer, citations: m.citations }))))
      .catch(() => {});
  }, [investigation.investigation_id]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [messages]);

  async function submit(ev) {
    ev.preventDefault();
    const q = question.trim();
    if (!q) return;
    setQuestion("");
    try {
      const result = await withBusy("Retrieving evidence and asking the model…", () =>
        apiPost(`/api/investigations/${investigation.investigation_id}/chat`, { question: q, actor: "reviewer" })
      );
      setMessages((prev) => [...prev, { question: q, answer: result.answer, citations: result.citations, error: result.error }]);
    } catch (e) {
      /* status shows error */
    }
  }

  return (
    <div>
      <h2>Ask the Copilot</h2>
      <p className="hint">
        Answers are grounded only in this signal's evidence, with click-navigable citations. Read-only: the chatbot
        never changes the recommendation.
      </p>
      <div ref={logRef}>
        {messages.map((m, i) => (
          <React.Fragment key={i}>
            <div className="chat-msg user"><strong>You:</strong> {m.question}</div>
            <div className="chat-msg assistant">
              <strong>Copilot:</strong> {m.answer}
              {m.error && <p className="fact-unverified-note">{"⚠"} {m.error}</p>}
              <div>
                {(m.citations || []).map((c, j) =>
                  c.verified ? (
                    <button
                      key={j}
                      type="button"
                      className="citation-chip"
                      onClick={() => onNavigateToEvidence(c.case_id, c.char_start, c.char_end)}
                    >
                      {c.case_id}
                    </button>
                  ) : (
                    <span key={j} className="citation-chip unverified">{c.case_id} &ndash; unverified</span>
                  )
                )}
              </div>
            </div>
          </React.Fragment>
        ))}
      </div>
      <form onSubmit={submit}>
        <label htmlFor="chat-input">Ask a question about this signal</label>
        <div className="chat-input-row">
          <input
            type="text"
            id="chat-input"
            required
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Did any patients have a positive rechallenge?"
          />
          <button type="submit">Ask</button>
        </div>
      </form>
    </div>
  );
}
