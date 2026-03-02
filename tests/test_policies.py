from app.policies import enforce_no_cite_no_claim


def test_no_cite_no_claim():
    report = "## Summary\n\nThis is a claim without cite.\n\n## Sources\n\n- [1] x"
    ok, issues = enforce_no_cite_no_claim(report)
    assert not ok
    assert issues


def test_with_citations_ok():
    report = "## Summary\n\nThis is a cited claim. [1]\n\n## Sources\n\n- [1] x"
    ok, issues = enforce_no_cite_no_claim(report)
    assert ok
    assert issues == []
