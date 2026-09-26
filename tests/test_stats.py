from backend.stats.disproportionality import compute_signal_stats, build_contingency_table


def test_contingency_table_basic():
    reports = [
        {"drug": "A", "event": "X"}, {"drug": "A", "event": "X"},
        {"drug": "A", "event": "Y"}, {"drug": "B", "event": "X"},
        {"drug": "B", "event": "Y"},
    ]
    t = build_contingency_table(reports, "A", "X")
    assert (t.a, t.b, t.c, t.d) == (2, 1, 1, 1)


def test_stats_deterministic_and_evans():
    reports = [{"drug": "A", "event": "X"} for _ in range(10)]
    reports += [{"drug": "A", "event": "Y"} for _ in range(2)]
    reports += [{"drug": "B", "event": "X"} for _ in range(1)]
    reports += [{"drug": "B", "event": "Y"} for _ in range(50)]

    s1 = compute_signal_stats(reports, "A", "X")
    s2 = compute_signal_stats(reports, "A", "X")
    assert s1.as_dict() == s2.as_dict()  # pure function: identical in -> identical out
    assert s1.a == 10
    assert s1.prr > 2
    assert s1.is_signal is True


def test_no_signal_when_below_evans_case_count():
    reports = [{"drug": "A", "event": "X"} for _ in range(2)]
    reports += [{"drug": "B", "event": "Y"} for _ in range(100)]
    s = compute_signal_stats(reports, "A", "X")
    assert s.a == 2
    assert s.is_signal is False  # a < 3 fails Evans case-count criterion
