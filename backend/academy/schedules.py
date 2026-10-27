from datetime import date, datetime, timedelta

from django.utils import timezone

from .models import ClassSchedule


def get_next_class_occurrence(
    schedule: ClassSchedule,
    *,
    reference: datetime | None = None,
    not_before: date | None = None,
) -> datetime:
    """Return the next enrolled weekly start time in the configured timezone."""
    current_time = timezone.localtime(reference) if reference else timezone.localtime()
    first_possible_date = max(current_time.date(), not_before or current_time.date())
    days_until_class = (schedule.weekday - first_possible_date.weekday()) % 7
    class_date = first_possible_date + timedelta(days=days_until_class)
    class_start = timezone.make_aware(
        datetime.combine(class_date, schedule.start_time),
        timezone.get_current_timezone(),
    )
    if class_start <= current_time:
        class_start += timedelta(days=7)
    return class_start
