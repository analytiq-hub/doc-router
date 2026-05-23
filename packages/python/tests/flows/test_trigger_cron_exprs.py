"""Unit tests for schedule/poll cron expression helpers."""

import pytest

from analytiq_data.flows.triggers.cron_exprs import (
    CronExpressionError,
    poll_times_to_crons,
    schedule_params_to_crons,
    schedule_rule_to_cron,
    validate_cron_expression,
)


def test_schedule_minutes_interval():
    assert schedule_rule_to_cron({"field": "minutes", "minutesInterval": 5}) == "*/5 * * * *"


def test_schedule_hours_interval():
    assert schedule_rule_to_cron({"field": "hours", "hoursInterval": 2}) == "0 */2 * * *"


def test_schedule_days_interval():
    assert schedule_rule_to_cron({"field": "days", "daysInterval": 1}) == "0 0 */1 * *"


def test_schedule_custom_cron():
    assert schedule_rule_to_cron({"field": "cronExpression", "cronExpression": "15 4 * * *"}) == "15 4 * * *"


def test_schedule_params_multiple_rules():
    params = {
        "rule": {
            "interval": [
                {"field": "hours", "hoursInterval": 1},
                {"field": "cronExpression", "cronExpression": "0 9 * * 1-5"},
            ]
        }
    }
    assert schedule_params_to_crons(params) == ["0 */1 * * *", "0 9 * * 1-5"]


def test_poll_times_default_every_minute():
    assert poll_times_to_crons(None) == ["* * * * *"]


def test_poll_times_custom():
    assert poll_times_to_crons({"item": [{"mode": "custom", "cronExpression": "0 */2 * * *"}]}) == [
        "0 */2 * * *"
    ]


def test_invalid_cron_raises():
    with pytest.raises(CronExpressionError):
        validate_cron_expression("not a cron")


def test_croniter_accepts_six_field_expression():
    assert validate_cron_expression("0 * * * * 1") == "0 * * * * 1"


def test_croniter_accepts_reverse_range_in_weekday_field():
    assert validate_cron_expression("0 * * * 1,2,3-1") == "0 * * * 1,2,3-1"


def test_valid_range_accepted():
    assert validate_cron_expression("0 * * * 1-3") == "0 * * * 1-3"
