from decimal import Decimal
from uuid import uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import DecimalValidator
from django.db import transaction
from django.db.models import Sum

from academy.models import Student
from payments.models import CreditRelease, PaymentAllocation

from .models import ChargeAdjustment, MonthlyCharge
from .queries import charges_with_economic_totals

PREVIEW_SALT = "billing.charge-adjustment"


def _require_adjustment_permission(actor):
    if (
        not actor.is_active
        or not actor.is_staff
        or not actor.has_perm("billing.adjust_monthlycharge")
    ):
        raise PermissionDenied


def _lock_charge(charge_id):
    student_id = MonthlyCharge.objects.values_list("student_id", flat=True).get(
        pk=charge_id
    )
    Student.objects.select_for_update().get(pk=student_id)
    MonthlyCharge.objects.select_for_update().get(pk=charge_id)
    return (
        charges_with_economic_totals()
        .select_related("student", "discipline")
        .get(pk=charge_id)
    )


def _charge_state(charge):
    return {
        "adjustment": charge.adjustments.order_by("-pk")
        .values_list("pk", flat=True)
        .first(),
        "allocations": list(
            charge.payment_allocations.order_by("pk").values_list("pk", flat=True)
        ),
        "total": str(charge.current_amount),
        "paid": str(charge.paid_amount),
    }


def _target_amount(charge, resulting_amount, reverses_id):
    if reverses_id:
        try:
            original = ChargeAdjustment.objects.get(pk=reverses_id, charge=charge)
        except ChargeAdjustment.DoesNotExist as exc:
            raise ValidationError(
                "El ajuste a compensar no pertenece a esta mensualidad."
            ) from exc
        if ChargeAdjustment.objects.filter(reverses=original).exists():
            raise ValidationError("Este ajuste ya fue compensado.")
        resulting_amount = charge.current_amount - original.difference
    if not isinstance(resulting_amount, Decimal) or not resulting_amount.is_finite():
        raise ValidationError("Ingresá un importe decimal válido.")
    DecimalValidator(12, 2)(resulting_amount)
    if resulting_amount < 0:
        raise ValidationError("El total resultante no puede ser negativo.")
    if resulting_amount == charge.current_amount:
        raise ValidationError("El nuevo importe debe ser distinto del total actual.")
    return resulting_amount.quantize(Decimal("0.01"))


@transaction.atomic
def preview_charge_adjustment(
    *,
    charge_id: int,
    resulting_amount: Decimal | None,
    reason: str,
    actor,
    reverses_id: int | None = None,
) -> dict:
    """Bind an administrative preview to its actor, exact inputs and charge state.

    A short student lock provides a consistent preview. Confirmation must acquire
    the same lock and reject intervening payments or adjustments.
    """
    _require_adjustment_permission(actor)
    reason = reason.strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("Ingresá un motivo de entre 1 y 1000 caracteres.")
    charge = _lock_charge(charge_id)
    resulting_amount = _target_amount(charge, resulting_amount, reverses_id)
    payload = {
        "operation": str(uuid4()),
        "actor": actor.pk,
        "charge": charge.pk,
        "result": str(resulting_amount),
        "reason": reason,
        "reverses": reverses_id,
        "state": _charge_state(charge),
    }
    return {
        "token": signing.dumps(payload, salt=PREVIEW_SALT),
        "original": charge.amount,
        "previous": charge.current_amount,
        "paid": charge.paid_amount,
        "balance": charge.outstanding,
        "result": resulting_amount,
        "difference": resulting_amount - charge.current_amount,
        "credit": max(charge.paid_amount - resulting_amount, Decimal("0.00")),
        "resulting_balance": max(
            resulting_amount - charge.paid_amount, Decimal("0.00")
        ),
        "reason": reason,
    }


@transaction.atomic
def confirm_charge_adjustment(
    *, preview_token: str, actor, charge_id: int
) -> ChargeAdjustment:
    """Append an adjustment and release excess money once, or roll back both.

    Replay uses the signed operation identity before stale-state validation.
    Released money is never automatically reclaimed by later increases.
    """
    _require_adjustment_permission(actor)
    try:
        payload = signing.loads(preview_token, salt=PREVIEW_SALT)
    except signing.BadSignature as exc:
        raise ValidationError(
            "La vista previa no es válida. Revisá los valores nuevamente."
        ) from exc
    if payload["actor"] != actor.pk or payload["charge"] != charge_id:
        raise PermissionDenied
    charge = _lock_charge(payload["charge"])
    existing = ChargeAdjustment.objects.filter(
        operation_id=payload["operation"]
    ).first()
    if existing:
        if (
            existing.charge_id != charge.pk
            or existing.created_by_id != actor.pk
            or existing.resulting_amount != Decimal(payload["result"])
            or existing.reason != payload["reason"]
            or existing.reverses_id != payload["reverses"]
        ):
            raise ValidationError("La operación ya existe con otros datos.")
        return existing
    try:
        signing.loads(preview_token, salt=PREVIEW_SALT, max_age=3600)
    except signing.SignatureExpired as exc:
        raise ValidationError(
            "La vista previa venció. Revisá los valores nuevamente."
        ) from exc
    if payload["state"] != _charge_state(charge):
        raise ValidationError(
            "La mensualidad cambió desde la vista previa. "
            "Revisá los valores actuales antes de confirmar."
        )
    resulting_amount = _target_amount(
        charge, Decimal(payload["result"]), payload["reverses"]
    )
    adjustment = ChargeAdjustment(
        charge=charge,
        previous_amount=charge.current_amount,
        resulting_amount=resulting_amount,
        difference=resulting_amount - charge.current_amount,
        reason=payload["reason"],
        created_by=actor,
        operation_id=payload["operation"],
        reverses_id=payload["reverses"],
    )
    adjustment.save(_from_adjustment_service=True)
    remaining = max(charge.paid_amount - resulting_amount, Decimal("0.00"))
    # PK reflects application order even when the receipt date was backdated.
    allocations = PaymentAllocation.objects.filter(charge=charge).order_by("-pk")
    released_by_allocation = {
        row["allocation_id"]: row["total"]
        for row in CreditRelease.objects.filter(allocation__charge=charge)
        .values("allocation_id")
        .annotate(total=Sum("amount"))
    }
    for allocation in allocations:
        if remaining == 0:
            break
        available = allocation.amount - released_by_allocation.get(
            allocation.pk, Decimal("0.00")
        )
        released = min(remaining, available)
        if released > 0:
            CreditRelease(
                adjustment=adjustment, allocation=allocation, amount=released
            ).save(_from_adjustment_service=True)
            remaining -= released
    if remaining:
        raise ValidationError(
            "No se pudo identificar el dinero a liberar. No se guardó el ajuste."
        )
    return adjustment
