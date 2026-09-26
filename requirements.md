# Requirements: AI Signal Investigation Copilot

## Introduction

Pharmacovigilance (PV) safety scientists must detect and investigate **safety signals**: drug–event
pairs reported more often than expected. Today, once a statistical signal appears, a scientist
manually reads every underlying case narrative to judge time-to-onset, dechallenge/rechallenge,
confounders and alternative causes, assigns causality per case, and writes an investigation
summary defensible to a regulator. This is slow (assumed ~15–20 min per case), inconsistent
between analysts, and hard to audit.

The Copilot removes the labour-intensive reading and structuring work while keeping every
regulatory decision deterministic and human-approved:

- **Statistics detect** (PRR / ROR / chi-square, deterministic).
- **AI extracts** facts from narratives with verbatim, machine-verified evidence quotes.
- **Rules decide** causality and the signal recommendation (versioned, pure functions).
- **Humans approve**: reviewers can override any AI-derived fact or decision, with a reason, and sign off.
- **Every AI claim is anchored**: guardrails operate at two levels — prompt-level (instructing the model) and system-level (deterministic code that verifies and cannot be talked out of) — so nothing reaches a reviewer unverified.
- **Reviewers can ask** a retrieval-grounded chatbot to dig deeper into the signal, and every answer cites the case evidence it came from.

### Stated assumptions (for the presentation)

- A1. All data is synthetic, FAERS-style; no real patient data is used.
- A2. Drug names are fictional; event terms are MedDRA-like Preferred Terms (no licensed dictionary).
- A3. The causality rule is a simplified, WHO-UMC-inspired rule set, not a validated clinical algorithm.
- A4. Manual effort baseline (minutes per case) is a configurable assumption used for the time-saved metric.
- A5. Single-user local prototype; authentication is out of scope and flagged as such.
- A6. LLM: Amazon Bedrock Nova Lite (`apac.amazon.nova-lite-v1:0`, `ap-south-1`), temperature 0.

### Glossary

- **Signal**: a drug–event pair meeting the disproportionality threshold.
- **PRR / ROR**: Proportional Reporting Ratio / Reporting Odds Ratio, computed from a 2×2 contingency table.
- **Evans criteria**: PRR ≥ 2, chi-square ≥ 4, case count ≥ 3.
- **Dechallenge / Rechallenge**: outcome when the drug is stopped / reintroduced.
- **Evidence quote**: a verbatim substring of the source narrative supporting an extracted fact.
- **Prompt guardrail**: an instruction embedded in the model prompt that constrains behaviour (e.g. "only report facts, never assign causality", "quote verbatim"). Reduces but cannot eliminate hallucination.
- **System guardrail**: deterministic, non-LLM code that verifies model output against ground truth (e.g. substring verification, schema validation, citation existence checks). The model cannot argue its way past it.
- **Knowledge base (KB)**: the structured, evidence-anchored store of a signal's cases, facts, quotes and statistics that the chatbot retrieves over.
- **RAG**: Retrieval-Augmented Generation — the chatbot answers only from chunks retrieved from the KB, not from free recall.
- **Summary vector**: an embedding of a case-level summary, used for coarse retrieval before drilling into chunk-level evidence.

---

## Requirements

### Requirement 1: Synthetic safety dataset

**User story:** As a presenter, I want a realistic synthetic adverse-event dataset, so that the demo is safe and shows a genuine signal.

1. THE system SHALL generate a reproducible (fixed seed) dataset of ≥1,000 FAERS-style reports, each with report ID, drug, event term, age, sex, seriousness, country, received date and a free-text narrative.
2. THE dataset SHALL contain at least one planted true signal (strong causal features in narratives) and at least one planted confounded signal (statistically flagged, but narratives dominated by alternative causes).
3. Causal features (onset timing, dechallenge, rechallenge, confounders) SHALL exist only in the free-text narrative, not as structured fields, so that extraction is genuinely required.

### Requirement 2: Deterministic signal detection

**User story:** As a safety scientist, I want drug–event pairs automatically ranked by disproportionality, so that I don't manually build contingency tables.

1. THE system SHALL compute, for every drug–event pair with ≥1 report: case count (a), PRR, ROR with 95% CI, and chi-square.
2. THE system SHALL flag a pair as a signal WHEN it meets the Evans criteria.
3. THE computation SHALL be a pure function: identical data SHALL always produce identical results.
4. THE UI SHALL display flagged signals ranked by PRR, with the 2×2 table visible on request.

### Requirement 3: AI case-level fact extraction

**User story:** As a safety scientist, I want the AI to read each case narrative in a signal and extract causality-relevant facts, so that I don't read dozens of narratives by hand.

1. WHEN the user starts an investigation on a signal, THE system SHALL send each underlying narrative to the LLM and extract: time-to-onset (days or unknown), temporal relationship, dechallenge result, rechallenge result, alternative causes/confounders, and data gaps.
2. THE LLM call SHALL use temperature 0 and forced structured output (tool/JSON schema); non-conforming output SHALL be rejected and recorded as an extraction failure, never silently accepted.
3. Each non-"unknown" fact SHALL include a verbatim evidence quote from the narrative.
4. THE LLM SHALL NOT assign causality or recommendations; it only reports facts.
5. Extraction SHALL run cases concurrently so that a signal of ~40 cases completes in under ~60 seconds.

### Requirement 4: Two-level anti-hallucination guardrails

**User story:** As a reviewer, I want anti-hallucination protection at both the prompt level and the system level, so that I understand that the model is instructed to behave AND that deterministic code independently verifies it, and nothing invented can reach me unchallenged.

**Level 1 — Prompt guardrails (necessary, not sufficient):**

1. THE extraction prompt SHALL instruct the model to: report only facts (never assign causality or recommendations), quote evidence verbatim, and return "unknown" rather than infer when the narrative does not state a fact.
2. THE prompt version SHALL be recorded on every extraction so that prompt-level guardrails are themselves versioned and auditable.
3. THE system SHALL treat prompt guardrails as fallible: no fact SHALL be trusted on the strength of the prompt alone; every fact SHALL additionally pass the Level 2 system guardrails.

**Level 2 — System guardrails (deterministic, authoritative):**

4. THE system SHALL verify each evidence quote is a substring of its source narrative (whitespace/case-normalised) using non-LLM code.
5. THE system SHALL validate every extraction against the forced output schema; non-conforming output SHALL be rejected as an extraction failure (per Requirement 3), never coerced or silently accepted.
6. IF a quote fails verification, THEN THE system SHALL downgrade that fact to "unknown", mark it "unverified", and surface it to the reviewer.
7. THE system SHALL record, per extraction, the guardrail outcome (quotes verified, quotes rejected, schema valid/invalid) so the anti-hallucination check is itself auditable and measurable.

### Requirement 4a: Evidence navigation UI (click evidence → jump to source)

**User story:** As a reviewer, I want to click any AI-derived fact or citation and be taken directly to the exact supporting text in the source, so that I can confirm the evidence in one action without hunting through narratives.

1. WHEN the reviewer selects a fact, THE UI SHALL scroll to and highlight the verified evidence quote within the source narrative, located by character offset (not by re-searching text at render time).
2. Each highlighted quote SHALL identify its source (case ID) and remain visually distinct from surrounding text without relying on colour alone.
3. WHEN a fact's quote is unverified or the fact is "unknown", THE UI SHALL make that state explicit and SHALL NOT present a false highlight.
4. Every citation surfaced by the chatbot (Requirement 12) SHALL be click-navigable to its source quote using the same mechanism.
5. Evidence navigation SHALL be keyboard-operable and expose the selected quote's source to assistive technology.

### Requirement 5: Deterministic, versioned causality rules

**User story:** As a safety scientist, I want causality assigned by a transparent rule, so that the same facts always yield the same category and it is defensible at inspection.

1. THE system SHALL assign each case a causality category (Certain, Probable, Possible, Unlikely, Unassessable) using a versioned rule set applied to the verified facts.
2. Each assignment SHALL record the rule ID, rule-set version, and a plain-language explanation of which facts fired it.
3. THE rules SHALL be pure functions with no LLM involvement.

### Requirement 6: Deterministic signal recommendation

**User story:** As a safety scientist, I want a recommendation computed from statistics and case causality, so that the conclusion is consistent across analysts.

1. THE system SHALL compute a recommendation (e.g. *Validated – escalate to Safety Review Committee*, *Not confirmed – confounded, continue monitoring*, *Insufficient information – request follow-up*) from the signal statistics and the causality distribution, via a versioned rule.
2. THE recommendation SHALL be recomputed immediately WHEN a reviewer overrides any case.
3. THE recommendation SHALL display the rule ID, version and the thresholds that drove it.

### Requirement 7: AI-drafted investigation summary

**User story:** As a safety scientist, I want a drafted investigation narrative, so that I don't write the report from scratch.

1. THE system SHALL generate a draft summary from the structured facts, statistics and the rule-computed recommendation (not from raw free reasoning).
2. THE summary SHALL cite case IDs; THE system SHALL verify every cited case ID exists in the signal and flag any that do not.
3. THE summary SHALL be clearly labelled "AI draft – requires human approval" and SHALL NOT change the recommendation.

### Requirement 8: Human-in-the-loop review and sign-off

**User story:** As a reviewer, I want to accept or override AI-derived facts and causality with a reason, and formally sign off, so that a qualified human owns every decision.

1. THE reviewer SHALL be able to override any case's causality category; an override SHALL require a reason.
2. THE UI SHALL visually distinguish AI-derived, rule-derived and human-overridden values.
3. THE reviewer SHALL be able to edit the draft summary and sign off with name and final decision (accept recommendation / override recommendation with reason).
4. THE system SHALL NOT mark an investigation complete without human sign-off.

### Requirement 9: Audit trail and deterministic replay

**User story:** As a QA/inspection lead, I want a tamper-evident record of every AI call, rule decision and human action, so that the investigation can be reconstructed.

1. THE system SHALL append an audit event for each AI extraction, rule evaluation, override and sign-off, including model ID, prompt version, rule version, actor and timestamp.
2. Audit events SHALL be hash-chained (each event includes the previous event's SHA-256); THE system SHALL expose a chain-verification check.
3. THE system SHALL cache extractions keyed by hash(model ID + prompt version + narrative), so that re-running an investigation reproduces identical facts without new LLM calls.

### Requirement 10: Effort-reduction metrics

**User story:** As a presenter, I want to show time saved, so that the impact on manual work is concrete.

1. THE system SHALL display, per investigation: cases processed, AI processing time, facts extracted, quotes verified/rejected, and estimated manual time saved (cases × assumed minutes per case, labelled as an assumption).

### Requirement 11: Demo operability

**User story:** As a presenter, I want the demo to start with one command and survive network issues, so that the 7-minute demo is reliable.

1. THE app SHALL start with a single command and serve the UI and API from one local process.
2. IF the LLM is unreachable, THEN THE system SHALL fail loudly per case (visible error), and cached results SHALL still load.
3. THE UI SHALL meet basic accessibility: semantic HTML, keyboard-operable controls, labelled form fields, and not rely on colour alone for status.

### Requirement 12: Retrieval-grounded investigation chatbot (RAG)

**User story:** As a medical reviewer, I want to ask a chatbot follow-up questions about a signal and have it answer only from that signal's evidence with citations, so that I can dive deeper without reading every narrative and without trusting an ungrounded model.

**Knowledge base and retrieval:**

1. WHEN an investigation is run, THE system SHALL build a knowledge base for the signal from its cases: the source narratives, the verified facts, the evidence quotes, and the signal statistics.
2. THE KB SHALL be chunked and embedded into a vector store, with two granularities: a **summary vector** per case (embedding a case-level summary) for coarse retrieval, and chunk-level vectors for fine-grained evidence retrieval.
3. WHEN the reviewer asks a question, THE system SHALL retrieve relevant context via the vector store (summary vectors to select cases, then chunk vectors within them) and pass only the retrieved context to the LLM.
4. Retrieval SHALL be scoped to the current signal's KB; the chatbot SHALL NOT answer from other signals or from model general knowledge.

**Grounding and anti-hallucination (chatbot-specific guardrails):**

5. THE chatbot answer prompt SHALL instruct the model to answer only from the retrieved context and to say it cannot find the answer when the context does not support one (Level 1 guardrail).
6. Every substantive claim in an answer SHALL carry a citation to a KB item (case ID and evidence quote); THE system SHALL verify each cited quote exists in the KB via deterministic code and SHALL flag or strip any unverifiable citation (Level 2 guardrail).
7. IF retrieval returns no sufficiently relevant context, THEN THE chatbot SHALL say it has no supporting evidence rather than answer from general knowledge.
8. THE chatbot SHALL NOT assign causality or change the recommendation; it is read-only over the KB and clearly labelled as an assistant, not a decision-maker.

**Auditability and UX:**

9. THE system SHALL log each chatbot exchange (question, retrieved chunk IDs, model ID, prompt version, answer, citations) to the audit trail (per Requirement 9).
10. THE chatbot UI SHALL render citations as click-navigable evidence links (per Requirement 4a), so the reviewer can jump from an answer straight to the source text.
11. THE chatbot SHALL use temperature 0 for reproducibility, consistent with the rest of the system.

---

## Out of scope

- Real FAERS/EudraVigilance ingestion, MedDRA coding, E2B export.
- Authentication, multi-tenancy, production deployment.
- Training or fine-tuning models.
- Multi-format source ingestion (Excel, PDF/OCR, external databases) into the KB — the KB is built from the signal's own cases for now.
- A general-purpose or cross-signal chatbot — the chatbot is scoped to the current signal's KB only.
- Inference-level KV / prompt caching — result caching (Requirement 9.3) covers reproducibility; attention-level caching is a later optimisation.
