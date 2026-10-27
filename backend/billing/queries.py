from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from payments.models import CreditRelease, PaymentAllocation

from .models import ChargeAdjustment, MonthlyCharge


def charges_with_economic_totals(queryset=None):
    """Calculate debt from immutable charges, adjustments and retained allocations.

    Independent subqueries prevent multiplication when a charge has several
    payments and adjustments. Released money no longer covers its original charge.
    """
    if queryset is None:
        queryset = MonthlyCharge.objects.all()
    money = DecimalField(max_digits=12, decimal_places=2)
    zero = Value(Decimal("0.00"), output_field=money)
    adjustments = (
        ChargeAdjustment.objects.filter(charge_id=OuterRef("pk"))
        .order_by()
        .values("charge_id")
        .annotate(total=Sum("difference"))
        .values("total")
    )
    payments = (
        PaymentAllocation.objects.filter(charge_id=OuterRef("pk"))
        .order_by()
        .values("charge_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    releases = (
        CreditRelease.objects.filter(allocation__charge_id=OuterRef("pk"))
        .order_by()
        .values("allocation__charge_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return (
        queryset.annotate(
            adjustment_amount=Coalesce(Subquery(adjustments), zero),
            original_paid_amount=Coalesce(Subquery(payments), zero),
            released_amount=Coalesce(Subquery(releases), zero),
        )
        .annotate(
            current_amount=F("amount") + F("adjustment_amount"),
            paid_amount=F("original_paid_amount") - F("released_amount"),
        )
        .annotate(outstanding=F("current_amount") - F("paid_amount"))
    )


def students_with_available_credit(queryset):
    """Return per-student available money; 03A has no credit consumption yet."""
    releases = (
        CreditRelease.objects.filter(allocation__payment__student_id=OuterRef("pk"))
        .order_by()
        .values("allocation__payment__student_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )
    return queryset.annotate(
        available_credit=Coalesce(
            Subquery(releases),
            Value(
                Decimal("0.00"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
    )
