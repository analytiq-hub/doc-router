"""Unit tests for schedule/poll cron expression helpers."""

import pytest
from datetime import datetime, UTC

from analytiq_data.flows.triggers.cron_exprs import (
    CronExpressionError,
    next_anchored_run,
    poll_times_to_crons,
    poll_times_to_specs,
    schedule_params_to_crons,
    schedule_params_to_specs,
    schedule_rule_to_cron,
    schedule_rule_to_interval_seconds,
    schedule_rule_to_spec,
    validate_cron_expression,
)


def test_schedule_minutes_interval_seconds():
    assert schedule_rule_to_interval_seconds({"field": "minutes", "minutesInterval": 5}) == 300.0


def test_schedule_hours_interval_seconds():
    assert schedule_rule_to_interval_seconds({"field": "hours", "hoursInterval": 2}) == 7200.0


def test_schedule_days_interval_seconds():
    assert schedule_rule_to_interval_seconds({"field": "days", "daysInterval": 1}) == 86400.0


def test_schedule_rule_to_spec_interval():
    spec = schedule_rule_to_spec({"field": "minutes", "minutesInterval": 5}, 0)
    assert spec.kind == "interval"
    assert spec.interval_secs == 300.0


def test_schedule_rule_to_spec_cron():
    spec = schedule_rule_to_spec({"field": "cronExpression", "cronExpression": "15 4 * * *"}, 1)
    assert spec.kind == "cron"
    assert spec.cron_expr == "15 4 * * *"


def test_schedule_legacy_cron_helper_uses_placeholder_for_intervals():
    assert schedule_rule_to_cron({"field": "minutes", "minutesInterval": 5}) == "* * * * *"


def test_schedule_params_multiple_rules():
    params = {
        "rule": {
            "interval": [
                {"field": "hours", "hoursInterval": 1},
                {"field": "cronExpression", "cronExpression": "0 9 * * 1-5"},
            ]
        }
    }
    specs = schedule_params_to_specs(params)
    assert specs[0].kind == "interval"
    assert specs[0].interval_secs == 3600.0
    assert specs[1].kind == "cron"
    assert schedule_params_to_crons(params) == ["* * * * *", "0 9 * * 1-5"]


def test_next_anchored_run_from_configuration_time():
    anchor = datetime(2026, 5, 21, 10, 23, 47, tzinfo=UTC)
    after = datetime(2026, 5, 21, 10, 23, 50, tzinfo=UTC)
    nxt = next_anchored_run(anchor, 3600.0, after=after)
    assert nxt == datetime(2026, 5, 21, 11, 23, 47, tzinfo=UTC)


def test_next_anchored_run_when_after_equals_anchor():
    anchor = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
    nxt = next_anchored_run(anchor, 300.0, after=anchor)
    assert nxt == datetime(2026, 5, 21, 10, 5, 0, tzinfo=UTC)


def test_next_anchored_run_when_after_before_anchor():
    """Clock skew / tests: still schedule first fire at anchor + interval."""
    anchor = datetime(2026, 5, 21, 12, 0, 0, tzinfo=UTC)
    after = datetime(2026, 5, 21, 11, 0, 0, tzinfo=UTC)
    nxt = next_anchored_run(anchor, 3600.0, after=after)
    assert nxt == datetime(2026, 5, 21, 13, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "rule,msg",
    [
        ({"field": "minutes", "minutesInterval": 0}, "minutesInterval must be between 1 and 59"),
        ({"field": "minutes", "minutesInterval": 60}, "minutesInterval must be between 1 and 59"),
        ({"field": "hours", "hoursInterval": 0}, "hoursInterval must be between 1 and 23"),
        ({"field": "hours", "hoursInterval": 24}, "hoursInterval must be between 1 and 23"),
        ({"field": "days", "daysInterval": 0}, "daysInterval must be between 1 and 31"),
        ({"field": "days", "daysInterval": 32}, "daysInterval must be between 1 and 31"),
    ],
)
def test_schedule_interval_bounds(rule, msg):
    with pytest.raises(CronExpressionError) as exc:
        schedule_rule_to_interval_seconds(rule)
    assert str(exc.value) == msg


def test_poll_times_default_every_minute_interval():
    specs = poll_times_to_specs(None)
    assert len(specs) == 1
    assert specs[0].kind == "interval"
    assert specs[0].interval_secs == 60.0
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
