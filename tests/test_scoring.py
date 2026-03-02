from app.scoring import keyword_coverage


def test_coverage():
    cov = keyword_coverage(
        "kubernetes ingress 504",
        "kubernetes [1]\n\ningress [1]\n\n## Sources\n- [1] x",
    )
    assert cov > 0.5
