from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from academy.models import Discipline, Enrollment, Student

from .models import (
    DisciplinePrice,
    MonthlyCharge,
    Scholarship,
    calculate_scholarship_discount,
)


@dataclass(frozen=True)
class MonthlyChargeGenerationResult:
    """Summarize created charges and enrollment or tariff issues for one period."""

    period: date
    created: int
    existing: int
    omitted: int
    missing_prices: tuple[tuple[str, str], ...]
    eligibility_changed: tuple[str, ...]


@dataclass(frozen=True)
class MonthlyChargePeriodSummary:
    """Describe expected, existing, and currently priceable charges for a period."""

    period: date
    student_count: int
    expected_charge_count: int
    existing_charge_count: int
    pending_charge_count: int
    missing_price_disciplines: tuple[str, ...]


def _validate_billing_period(billing_period: date) -> None:
    if not isinstance(billing_period, date) or billing_period.day != 1:
        raise ValidationError(_("El período debe ser el primer día de un mes."))


def _get_monthly_charge_candidates(
    *, billing_period: date, enrollment_ids: Iterable[int] | None = None
) -> dict[tuple[int, int], Enrollment]:
    last_day = date(
        billing_period.year,
        billing_period.month,
        monthrange(billing_period.year, billing_period.month)[1],
    )
    eligible_enrollments = Enrollment.objects.filter(enrolled_at__lte=last_day).filter(
        Q(ended_at__isnull=True) | Q(ended_at__gte=billing_period)
    )
    if enrollment_ids is not None:
        eligible_enrollments = eligible_enrollments.filter(pk__in=enrollment_ids)

    candidate_enrollments = eligible_enrollments.select_related(
        "student", "discipline"
    ).order_by("student_id", "discipline_id", "-enrolled_at", "-pk")
    monthly_charge_candidates = {}
    for enrollment in candidate_enrollments:
        candidate_key = (enrollment.student_id, enrollment.discipline_id)
        monthly_charge_candidates.setdefault(candidate_key, enrollment)
    return monthly_charge_candidates


def _get_existing_monthly_charge_keys(
    *, billing_period: date, candidate_keys: Iterable[tuple[int, int]]
) -> set[tuple[int, int]]:
    student_ids = {student_id for student_id, _ in candidate_keys}
    discipline_ids = {discipline_id for _, discipline_id in candidate_keys}
    if not student_ids:
        return set()

    return set(
        MonthlyCharge.objects.filter(
            period=billing_period,
            student_id__in=student_ids,
            discipline_id__in=discipline_ids,
        ).values_list("student_id", "discipline_id")
    ) & set(candidate_keys)


def _get_price_ids_by_discipline(
    *, billing_period: date, discipline_ids: Iterable[int]
) -> dict[int, list[int]]:
    prices_by_discipline = defaultdict(list)
    discipline_prices = DisciplinePrice.objects.filter(
        discipline_id__in=discipline_ids,
        effective_month__lte=billing_period,
    ).order_by("discipline_id", "-effective_month")
    for discipline_price in discipline_prices:
        prices_by_discipline[discipline_price.discipline_id].append(
            discipline_price.pk
        )
    return prices_by_discipline


def get_monthly_charge_period_summary(
    *, billing_period: date
) -> MonthlyChargePeriodSummary:
    """Count charge candidates without changing enrollment or financial records."""
    _validate_billing_period(billing_period)
    monthly_charge_candidates = _get_monthly_charge_candidates(
        billing_period=billing_period
    )
    candidate_keys = set(monthly_charge_candidates)
    existing_charge_keys = _get_existing_monthly_charge_keys(
        billing_period=billing_period, candidate_keys=candidate_keys
    )
    price_ids_by_discipline = _get_price_ids_by_discipline(
        billing_period=billing_period,
        discipline_ids={discipline_id for _, discipline_id in candidate_keys},
    )
    missing_price_disciplines = {
        enrollment.discipline.name
        for candidate_key, enrollment in monthly_charge_candidates.items()
        if candidate_key not in existing_charge_keys
        and not price_ids_by_discipline.get(enrollment.discipline_id)
    }

    return MonthlyChargePeriodSummary(
        period=billing_period,
        student_count=len({student_id for student_id, _ in candidate_keys}),
        expected_charge_count=len(candidate_keys),
        existing_charge_count=len(existing_charge_keys),
        pending_charge_count=len(candidate_keys - existing_charge_keys),
        missing_price_disciplines=tuple(sorted(missing_price_disciplines)),
    )


def generate_monthly_charges(
    *, billing_period: date, enrollment_ids: Iterable[int] | None = None
) -> MonthlyChargeGenerationResult:
    """Generate full-month charges once per student and discipline.

    The operation snapshots the latest applicable versioned price and retains the
    existing per-charge transaction boundary. Missing prices and enrollments that
    cease to cover the period are omitted and reported; other valid charges continue.
    Existing charges are never updated. Pass ``enrollment_ids`` to apply this same
    operation to a newly created enrollment from Django Admin. A discipline row lock
    serializes tariff changes with the selection of the price snapshot.
    """
    _validate_billing_period(billing_period)
    last_day = date(
        billing_period.year,
        billing_period.month,
        monthrange(billing_period.year, billing_period.month)[1],
    )
    monthly_charge_candidates = _get_monthly_charge_candidates(
        billing_period=billing_period, enrollment_ids=enrollment_ids
    )
    candidate_keys = set(monthly_charge_candidates)
    existing_charge_keys = _get_existing_monthly_charge_keys(
        billing_period=billing_period, candidate_keys=candidate_keys
    )
    created_count = 0
    existing_count = len(existing_charge_keys)
    omitted_count = 0
    missing_prices = []
    eligibility_changed = []

    for candidate_key, selected_enrollment in monthly_charge_candidates.items():
        if candidate_key in existing_charge_keys:
            continue

        student_id, discipline_id = candidate_key
        try:
            with transaction.atomic():
                enrollment = (
                    Enrollment.objects.select_for_update()
                    .select_related("student", "discipline")
                    .get(pk=selected_enrollment.pk)
                )
                if enrollment.enrolled_at > last_day or (
                    enrollment.ended_at and enrollment.ended_at < billing_period
                ):
                    omitted_count += 1
                    eligibility_changed.append(
                        f"{enrollment.student} — {enrollment.discipline}"
                    )
                    continue

                if MonthlyCharge.objects.filter(
                    student_id=student_id,
                    discipline_id=discipline_id,
                    period=billing_period,
                ).exists():
                    existing_count += 1
                    continue

                Student.objects.select_for_update().get(pk=student_id)
                Discipline.objects.select_for_update().get(pk=discipline_id)
                applicable_price = (
                    DisciplinePrice.objects.select_for_update()
                    .filter(
                        discipline_id=discipline_id,
                        effective_month__lte=billing_period,
                    )
                    .order_by("-effective_month", "-pk")
                    .first()
                )

                if applicable_price is None:
                    omitted_count += 1
                    missing_prices.append(
                        (str(enrollment.student), enrollment.discipline.name)
                    )
                    continue

                applicable_scholarship = (
                    Scholarship.objects.select_for_update()
                    .filter(
                        student_id=student_id,
                        discipline_id=discipline_id,
                        start_month__lte=billing_period,
                    )
                    .filter(
                        Q(end_month__isnull=True) | Q(end_month__gte=billing_period)
                    )
                    .first()
                )
                scholarship_percentage = (
                    applicable_scholarship.percentage
                    if applicable_scholarship
                    else None
                )
                discount_amount = (
                    calculate_scholarship_discount(
                        base_amount=applicable_price.amount,
                        percentage=scholarship_percentage,
                    )
                    if scholarship_percentage is not None
                    else Decimal("0.00")
                )

                MonthlyCharge.objects.create(
                    student_id=student_id,
                    discipline_id=discipline_id,
                    enrollment=enrollment,
                    period=billing_period,
                    price_applied=applicable_price,
                    base_amount=applicable_price.amount,
                    scholarship_percentage=scholarship_percentage,
                    discount_amount=discount_amount,
                    amount=applicable_price.amount - discount_amount,
                    currency=applicable_price.currency,
                )
                created_count += 1
        except IntegrityError:
            if MonthlyCharge.objects.filter(
                student_id=student_id,
                discipline_id=discipline_id,
                period=billing_period,
            ).exists():
                existing_count += 1
            else:
                raise
        except ValidationError:
            if MonthlyCharge.objects.filter(
                student_id=student_id,
                discipline_id=discipline_id,
                period=billing_period,
            ).exists():
                existing_count += 1
            else:
                raise
        except Enrollment.DoesNotExist:
            omitted_count += 1
            eligibility_changed.append(
                f"{selected_enrollment.student} — {selected_enrollment.discipline}"
            )

    return MonthlyChargeGenerationResult(
        period=billing_period,
        created=created_count,
        existing=existing_count,
        omitted=omitted_count,
        missing_prices=tuple(missing_prices),
        eligibility_changed=tuple(eligibility_changed),
    )
