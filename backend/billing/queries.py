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
    return queryset.annotate(**charge_economic_total_expressions())


def charge_economic_total_expressions():
    """Build shared SQL expressions for charge totals and their components."""
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
    adjustment_amount = Coalesce(Subquery(adjustments), zero)
    original_paid_amount = Coalesce(Subquery(payments), zero)
    released_amount = Coalesce(Subquery(releases), zero)
    current_amount = F("amount") + adjustment_amount
    paid_amount = original_paid_amount - released_amount
    return {
        "adjustment_amount": adjustment_amount,
        "original_paid_amount": original_paid_amount,
        "released_amount": released_amount,
        "current_amount": current_amount,
        "paid_amount": paid_amount,
        "outstanding": current_amount - paid_amount,
    }


def sum_charge_economic_totals(queryset):
    """Aggregate shared per-charge economic expressions in the database."""
    expressions = charge_economic_total_expressions()
    component_totals = queryset.order_by().aggregate(
        original_amount=Sum("amount"),
        adjustment_amount=Sum(expressions["adjustment_amount"]),
        original_paid_amount=Sum(expressions["original_paid_amount"]),
        released_amount=Sum(expressions["released_amount"]),
    )
    original_amount = component_totals["original_amount"] or Decimal("0.00")
    adjustment_amount = component_totals["adjustment_amount"] or Decimal("0.00")
    original_paid_amount = component_totals["original_paid_amount"] or Decimal(
        "0.00"
    )
    released_amount = component_totals["released_amount"] or Decimal("0.00")
    current_amount = original_amount + adjustment_amount
    paid_amount = original_paid_amount - released_amount
    return {
        "current_amount": current_amount,
        "paid_amount": paid_amount,
        "outstanding": current_amount - paid_amount,
    }


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
