from app.triage import _build_triage_prompt


def test_prior_context_injected_into_prompt() -> None:
    prompt = _build_triage_prompt(
        title="Payment timeout",
        description="Checkout fails with 504",
        search_paths=["src/PaymentProcessor/"],
        affected_services=["PaymentProcessor"],
        severity="P0",
        category="payment",
        eshop_map_path="/nonexistent",
        eshop_readme_path="/nonexistent",
        prior_context={
            "root_cause": "Connection pool exhaustion in PaymentProcessor",
            "suggested_fix": "Increase pool size in appsettings.json",
            "similarity": 0.85,
        },
    )

    assert "## Prior Incident Context" in prompt
    assert "Connection pool exhaustion" in prompt
    assert "Increase pool size" in prompt
    assert "UNVERIFIED HYPOTHESIS" in prompt
    assert "85%" in prompt


def test_no_prior_context_omits_section() -> None:
    prompt = _build_triage_prompt(
        title="Payment timeout",
        description="Checkout fails with 504",
        search_paths=["src/PaymentProcessor/"],
        affected_services=["PaymentProcessor"],
        severity="P0",
        category="payment",
        eshop_map_path="/nonexistent",
        eshop_readme_path="/nonexistent",
    )

    assert "## Prior Incident Context" not in prompt
