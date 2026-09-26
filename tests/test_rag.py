VOCAB = ["hepatic", "onset", "dechallenge", "kidney"]


def fake_embed(text: str) -> list[float]:
    t = text.lower()
    return [float(t.count(w)) + 0.01 for w in VOCAB]


def _seed_kb(investigation_id="INV-1"):
    from backend.kb.vectorstore import add_chunk
    add_chunk("s1", investigation_id, "RPT-1", "case_summary", "hepatic failure onset dechallenge",
              None, None, "summary", fake_embed("hepatic failure onset dechallenge"))
    add_chunk("c1", investigation_id, "RPT-1", "narrative", "onset was 3 days after starting the drug",
              0, 20, "chunk", fake_embed("onset was 3 days after starting the drug dechallenge hepatic"))


def test_no_relevant_context_returns_no_evidence_without_llm_call(fresh_db):
    _seed_kb()
    from backend.chatbot.rag import answer_question, NO_EVIDENCE_MESSAGE

    def boom(*a, **k):
        raise AssertionError("chat_fn should not be called when context is insufficient")

    result = answer_question(
        "INV-1", "what is the weather today", model_id="fake-model",
        embed_fn=lambda t: [0.0, 0.0, 0.0, 0.0],  # no overlap with any chunk -> low similarity
        chat_fn=boom,
    )
    assert result.had_sufficient_context is False
    assert result.answer == NO_EVIDENCE_MESSAGE


def test_valid_citation_is_verified_and_navigable(fresh_db):
    _seed_kb()
    from backend.chatbot.rag import answer_question

    def fake_chat(**kwargs):
        return "The event began 3 days after starting the drug [RPT-1]."

    result = answer_question("INV-1", "when did onset occur", model_id="fake-model",
                              embed_fn=fake_embed, chat_fn=fake_chat)
    assert result.had_sufficient_context is True
    assert len(result.citations) == 1
    assert result.citations[0]["verified"] is True
    assert result.citations[0]["case_id"] == "RPT-1"
    assert result.citations[0]["char_start"] is not None


def test_fabricated_citation_is_flagged_not_trusted(fresh_db):
    _seed_kb()
    from backend.chatbot.rag import answer_question

    def fake_chat(**kwargs):
        return "This affected patient [RPT-999], who was never actually retrieved."

    result = answer_question("INV-1", "onset dechallenge hepatic", model_id="fake-model",
                              embed_fn=fake_embed, chat_fn=fake_chat)
    assert result.had_sufficient_context is True
    assert result.citations[0]["case_id"] == "RPT-999"
    assert result.citations[0]["verified"] is False
    assert "unverified" in result.answer
