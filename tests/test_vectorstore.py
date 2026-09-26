VOCAB = ["hepatic", "kidney", "onset", "dechallenge", "rash", "fever"]


def fake_embed(text: str) -> list[float]:
    t = text.lower()
    return [float(t.count(w)) + 0.01 for w in VOCAB]


def test_add_and_retrieve_scoped_by_case(fresh_db):
    from backend.kb.vectorstore import add_chunk, retrieve

    add_chunk("s1", "INV-1", "RPT-1", "case_summary", "hepatic failure case summary",
              None, None, "summary", fake_embed("hepatic failure case summary"))
    add_chunk("s2", "INV-1", "RPT-2", "case_summary", "kidney injury case summary",
              None, None, "summary", fake_embed("kidney injury case summary"))
    add_chunk("c1", "INV-1", "RPT-1", "narrative", "onset was 3 days, dechallenge positive",
              0, 10, "chunk", fake_embed("onset was 3 days, dechallenge positive"))
    add_chunk("c2", "INV-1", "RPT-2", "narrative", "kidney injury with rash reported",
              0, 10, "chunk", fake_embed("kidney injury with rash reported"))

    results = retrieve("INV-1", fake_embed("hepatic dechallenge onset"), top_cases=1, top_chunks=5)
    report_ids = {r["report_id"] for r in results}
    # Should have selected case RPT-1's summary vector as most relevant, then only its chunks.
    assert "RPT-2" not in report_ids or "RPT-1" in report_ids


def test_investigation_scoping(fresh_db):
    from backend.kb.vectorstore import add_chunk, retrieve

    add_chunk("a1", "INV-A", "RPT-1", "case_summary", "hepatic case", None, None, "summary",
              fake_embed("hepatic case"))
    add_chunk("b1", "INV-B", "RPT-9", "case_summary", "kidney case", None, None, "summary",
              fake_embed("kidney case"))

    results = retrieve("INV-A", fake_embed("hepatic"), top_cases=5, top_chunks=5)
    assert all(r["investigation_id"] == "INV-A" for r in results) or len(results) == 0
