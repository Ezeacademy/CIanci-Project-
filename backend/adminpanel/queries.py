from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from academy.models import ClassSchedule, Student
from billing.models import MonthlyCharge
from billing.queries import charges_with_economic_totals
from payments.models import PaymentIntent

from .permissions import has_admin_permission


def get_admin_dashboard_data(user) -> dict:
    """Build private operational indicators using each domain's existing rules."""
    today = timezone.localdate()
    total_outstanding = charges_with_economic_totals(
        MonthlyCharge.objects.all()
    ).filter(outstanding__gt=0).aggregate(total=Sum("outstanding"))["total"]

    links = {
        "students": (
            "/admin-panel/alumnos"
            if all(
                has_admin_permission(user, permission)
                for permission in (
                    "academy.view_student",
                    "academy.view_enrollment",
                    "academy.view_discipline",
                )
            )
            else None
        ),
        "guardians": _admin_link(
            user,
            "accounts.view_guardianrelationship",
            "admin:accounts_guardianrelationship_changelist",
        ),
        "disciplines": _admin_link(
            user, "academy.view_discipline", "admin:academy_discipline_changelist"
        ),
        "teachers": _admin_link(
            user, "academy.view_teacher", "admin:academy_teacher_changelist"
        ),
        "enrollments": (
            "/admin-panel/alumnos"
            if all(
                has_admin_permission(user, permission)
                for permission in (
                    "academy.view_student",
                    "academy.view_enrollment",
                    "academy.view_discipline",
                )
            )
            else None
        ),
        "monthlyCharges": (
            "/admin-panel/mensualidades"
            if all(
                has_admin_permission(user, permission)
                for permission in (
                    "billing.view_monthlycharge",
                    "billing.view_chargeadjustment",
                    "payments.view_payment",
                )
            )
            else None
        ),
        "chargeGeneration": _admin_link(
            user,
            "billing.add_monthlycharge",
            "admin:billing_monthlycharge_management",
            also_requires=(
                "billing.view_monthlycharge",
                "billing.view_disciplineprice",
            ),
        ),
        "transfers": _admin_link(
            user,
            "payments.view_paymentintent",
            "admin:payments_paymentintent_changelist",
        ),
        "canResolveTransfers": has_admin_permission(
            user, "payments.change_paymentintent"
        ),
        "cashPayments": _admin_link(
            user, "payments.add_payment", "admin:payments_payment_add"
        ),
        "payments": _admin_link(
            user, "payments.view_payment", "admin:payments_payment_changelist"
        ),
        "credits": _admin_link(
            user,
            "payments.view_creditrelease",
            "admin:payments_creditrelease_changelist",
        ),
    }
    return {
        "date": today.isoformat(),
        "activeStudents": Student.objects.filter(
            enrollments__ended_at__isnull=True
        ).distinct().count(),
        "outstandingAmount": format(total_outstanding or Decimal("0.00"), ".2f"),
        "pendingTransfers": PaymentIntent.objects.filter(
            status=PaymentIntent.Status.PENDING
        ).count(),
        "recurringSchedulesToday": ClassSchedule.objects.filter(
            weekday=today.weekday(), is_active=True, teacher__is_active=True
        ).count(),
        "links": links,
    }


def _admin_link(user, permission: str, url_name: str, *, also_requires=()):
    """Expose a Django Admin destination only when its own gate will allow entry."""
    if not has_admin_permission(user, permission):
        return None
    if any(not has_admin_permission(user, required) for required in also_requires):
        return None
    return reverse(url_name)
