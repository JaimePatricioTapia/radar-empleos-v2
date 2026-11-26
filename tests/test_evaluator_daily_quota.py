from src.evaluation.evaluator import _daily_quota_retry_seconds


def test_daily_free_tier_quota_parses_hours_minutes_seconds():
    message = (
        "Generate content requests per day limit exceeded on Free Tier. "
        "Please retry in 22h9m16.450070893s."
    )
    assert _daily_quota_retry_seconds(message) == 22 * 3600 + 9 * 60 + 16.450070893


def test_daily_quota_without_retry_duration_uses_safe_24h_pause():
    message = "GenerateRequestsPerDayPerModel-FreeTier quota exceeded"
    assert _daily_quota_retry_seconds(message) == 24 * 3600


def test_non_daily_server_error_is_not_classified_as_daily_quota():
    assert _daily_quota_retry_seconds("503 UNAVAILABLE: high demand") is None
