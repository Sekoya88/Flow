import pytest
from datetime import datetime, timezone, timedelta


def test_schedule_is_due_first_run():
    """should consider schedule due when last_run_at is None"""
    from flow.application.scheduler import is_schedule_due
    assert is_schedule_due(cron_expr="* * * * *", last_run_at=None) is True


def test_schedule_not_due_when_run_recently():
    """should not be due when last run was just now (within the current minute tick)"""
    from flow.application.scheduler import is_schedule_due
    # Truncate to the current minute so croniter sees next_run = next minute, which is in the future
    now = datetime.now(timezone.utc)
    last_run = now.replace(second=0, microsecond=0)
    assert is_schedule_due(cron_expr="* * * * *", last_run_at=last_run) is False


def test_schedule_due_when_overdue():
    """should be due when last run was 90 seconds ago for '* * * * *' cron"""
    from flow.application.scheduler import is_schedule_due
    old = datetime.now(timezone.utc) - timedelta(seconds=90)
    assert is_schedule_due(cron_expr="* * * * *", last_run_at=old) is True
