from app.token_tracker import record_usage, get_summary, reset


def test_record_and_summarize_tokens() -> None:
    reset()
    record_usage(model="claude-sonnet-4-6", prompt_tokens=1500, completion_tokens=300)
    record_usage(model="mistral-medium-latest", prompt_tokens=200, completion_tokens=50)
    record_usage(model="claude-sonnet-4-6", prompt_tokens=1000, completion_tokens=200)

    summary = get_summary()
    assert summary["by_model"]["claude-sonnet-4-6"]["prompt_tokens"] == 2500
    assert summary["by_model"]["claude-sonnet-4-6"]["completion_tokens"] == 500
    assert summary["by_model"]["mistral-medium-latest"]["prompt_tokens"] == 200
    assert summary["total_prompt_tokens"] == 2700
    assert summary["total_completion_tokens"] == 550
    assert summary["estimated_cost_usd"] > 0
