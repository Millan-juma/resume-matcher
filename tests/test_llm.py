from app.services.llm import RuleBasedProvider, redact


def test_redact_removes_contact_details_but_keeps_dates():
    out = redact("Jane jane@x.com +254 712 345 678 worked 2020 - 2022")
    assert "jane@x.com" not in out and "712" not in out
    assert "2020 - 2022" in out


def test_rule_provider_reports_gaps():
    r = RuleBasedProvider().explain("resume", "job",
        {"matched_skills": ["python"], "missing_skills": ["docker"], "score": 50})
    assert any("docker" in g.lower() for g in r.gaps)
