import calendar
from datetime import date

from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from accounts.models import GuardianRelationship

from .models import Student


def _date_eighteen_years_ago(today):
    year = today.year - 18
    last_day = calendar.monthrange(year, today.month)[1]
    return date(year, today.month, min(today.day, last_day))


def accessible_students(user):
    if not user.is_authenticated:
        return Student.objects.none()

    cutoff = _date_eighteen_years_ago(timezone.localdate())
    current_guardianship = GuardianRelationship.objects.filter(
        guardian_id=user.pk,
        student_id=OuterRef("pk"),
        revoked_at__isnull=True,
    )
    return (
        Student.objects.annotate(_has_current_guardianship=Exists(current_guardianship))
        .filter(
            Q(user_id=user.pk)
            | Q(
                date_of_birth__isnull=False,
                date_of_birth__gt=cutoff,
                _has_current_guardianship=True,
            )
        )
        .order_by("last_name", "first_name", "pk")
    )
