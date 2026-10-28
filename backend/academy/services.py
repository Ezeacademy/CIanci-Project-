"""Shared academic operations used by Django Admin and private APIs."""

from calendar import monthrange
from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from billing.services import (
    MonthlyChargeGenerationResult,
    generate_monthly_charges,
)

from .models import Discipline, Enrollment, Student


@transaction.atomic
def create_student(*, first_name: str, last_name: str, date_of_birth=None) -> Student:
    """Create a student without creating or linking an authentication account."""
    student = Student(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        date_of_birth=date_of_birth,
    )
    student.full_clean()
    student.save()
    return student


@transaction.atomic
def create_enrollment(
    *, student_id: int, discipline_id: int, enrolled_at: date, actor, ended_at=None
) -> tuple[Enrollment, MonthlyChargeGenerationResult | None]:
    """Create an active enrollment and preserve the existing initial-charge rule.

    The database's conditional unique constraint is the final guard against two
    concurrent active enrollments for the same student and discipline.
    """
    student = Student.objects.select_for_update().get(pk=student_id)
    discipline = Discipline.objects.select_for_update().get(pk=discipline_id)
    if ended_at is None and not discipline.is_active:
        raise ValidationError({"discipline": _("La disciplina no está disponible.")})

    enrollment = Enrollment(
        student=student,
        discipline=discipline,
        enrolled_at=enrolled_at,
        ended_at=ended_at,
    )
    enrollment.full_clean()
    try:
        enrollment.save()
    except IntegrityError as error:
        raise ValidationError(
            {
                "discipline": _(
                    "El alumno ya tiene una inscripción activa en esta disciplina."
                )
            }
        ) from error

    charge_generation = None
    if actor.has_perm("billing.add_monthlycharge") and _covers_current_month(
        enrollment
    ):
        charge_generation = generate_monthly_charges(
            billing_period=timezone.localdate().replace(day=1),
            enrollment_ids=(enrollment.pk,),
        )
    return enrollment, charge_generation


def _covers_current_month(enrollment: Enrollment) -> bool:
    today = timezone.localdate()
    period_start = today.replace(day=1)
    period_end = date(
        period_start.year,
        period_start.month,
        monthrange(period_start.year, period_start.month)[1],
    )
    return not (
        enrollment.enrolled_at > today
        or enrollment.enrolled_at > period_end
        or (enrollment.ended_at and enrollment.ended_at < period_start)
    )


@transaction.atomic
def finish_enrollment(*, enrollment_id: int) -> Enrollment:
    """End an active enrollment today while retaining its historical record."""
    enrollment = Enrollment.objects.select_for_update().get(pk=enrollment_id)
    if enrollment.ended_at is not None:
        raise ValidationError({"enrollment": _("Esta inscripción ya fue finalizada.")})
    enrollment.ended_at = timezone.localdate()
    enrollment.full_clean()
    enrollment.save(update_fields=("ended_at",))
    return enrollment
