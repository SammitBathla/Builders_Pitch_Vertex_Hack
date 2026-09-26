"""Fictional drug names and MedDRA-like event terms (Assumption A2: no real drugs, no
licensed dictionary — these are invented but formatted like real Preferred Terms)."""

DRUGS = [
    "Zentrivex", "Mirocaine", "Vantrelex", "Quorabinib", "Dulastine", "Feniclor",
    "Xarontide", "Mirelvex", "Brintacor", "Sovaquin", "Trenaxafil", "Locivastin",
    "Oravex", "Klorimide", "Pentazine", "Ustovir", "Rimacept", "Axovantin",
    "Delunorix", "Halvorexin",
]

# True-signal pair: strong, consistent causal narrative pattern.
SIGNAL_DRUG_TRUE = "Zentrivex"
SIGNAL_EVENT_TRUE = "Acute Hepatic Failure"

# Confounded pair: statistically disproportionate but narratives point to alternative causes.
SIGNAL_DRUG_CONFOUNDED = "Mirocaine"
SIGNAL_EVENT_CONFOUNDED = "Acute Kidney Injury"

BACKGROUND_EVENTS = [
    "Nausea", "Headache", "Dizziness", "Fatigue", "Rash", "Pruritus", "Diarrhoea",
    "Vomiting", "Insomnia", "Arthralgia", "Myalgia", "Pyrexia", "Constipation",
    "Dyspepsia", "Anxiety", "Somnolence", "Peripheral Oedema", "Dry Mouth",
    "Palpitations", "Decreased Appetite",
]

ALL_EVENTS = BACKGROUND_EVENTS + [SIGNAL_EVENT_TRUE, SIGNAL_EVENT_CONFOUNDED]

COUNTRIES = [
    "United States", "United Kingdom", "Germany", "India", "Canada", "Australia",
    "France", "Japan", "Brazil", "South Africa",
]

SEX_VALUES = ["Female", "Male", "Unknown"]
SERIOUSNESS_VALUES = ["Serious", "Non-serious", "Serious - Life-threatening"]

ALTERNATIVE_CAUSES = [
    "a pre-existing history of chronic kidney disease",
    "concomitant use of a known nephrotoxic agent (ibuprofen, taken daily for chronic back pain)",
    "severe dehydration following several days of unrelated gastroenteritis",
    "poorly controlled diabetes with prior renal impairment",
    "a recent episode of sepsis requiring hospitalisation",
    "long-standing hypertension with baseline renal insufficiency",
    "concurrent use of a contrast-enhanced imaging procedure days earlier",
]

MINOR_CONFOUNDERS = [
    "a history of seasonal allergies",
    "occasional over-the-counter antihistamine use",
    "mild, well-controlled hypertension",
    "no other relevant medical history reported",
]
