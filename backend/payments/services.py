from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from academy.models import Student
from billing.models import MonthlyCharge

from .models import ARS, Payment, PaymentAllocation, PaymentIntent


def _normalize_allocations(allocations):
    normalized = {}
    for charge_id, amount in allocations:
        try:
            charge_id = int(charge_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError(_("Seleccioná un cargo válido.")) from exc
        amount = _to_decimal(amount)
        if amount <= 0:
            raise ValidationError(_("Cada asignación debe ser mayor que cero."))
        if charge_id in normalized:
            raise ValidationError(_("No repitas un cargo en la misma asignación."))
        normalized[charge_id] = amount
    if not normalized:
        raise ValidationError(_("Asigná el pago a por lo menos un cargo."))
    return normalized


def _to_decimal(amount):
    if isinstance(amount, float):
        raise ValidationError(_("Los importes deben expresarse como Decimal."))
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError(_("Ingresá un importe válido.")) from exc
    if not amount.is_finite():
        raise ValidationError(_("Ingresá un importe válido."))
    return amount


def _lock_and_validate_allocations(student_id, payment_amount, allocations):
    allocations = _normalize_allocations(allocations)
    allocated_total = sum(allocations.values(), Decimal("0.00"))
    if allocated_total != payment_amount:
        raise ValidationError(
            _("La suma de las asignaciones debe coincidir con el importe recibido.")
        )

    charges = list(
        MonthlyCharge.objects.select_for_update()
        .filter(pk__in=allocations)
        .order_by("pk")
    )
    if len(charges) != len(allocations):
        raise ValidationError(_("Uno o más cargos seleccionados ya no existen."))

    for charge in charges:
        if charge.student_id != student_id:
            raise ValidationError(
                _("Solo podés aplicar un pago a cargos del mismo alumno.")
            )

    already_paid = {
        row["charge_id"]: row["total"]
        for row in PaymentAllocation.objects.filter(charge_id__in=allocations)
        .values("charge_id")
        .annotate(total=Sum("amount"))
    }
    for charge in charges:
        balance = charge.amount - already_paid.get(charge.pk, Decimal("0.00"))
        if allocations[charge.pk] > balance:
            raise ValidationError(
                _("La asignación supera el saldo pendiente de %(charge)s.")
                % {"charge": charge}
            )

    return [(charge, allocations[charge.pk]) for charge in charges]


def _create_allocations(payment, allocations):
    for charge, amount in allocations:
        PaymentAllocation.objects.create(
            payment=payment,
            charge=charge,
            amount=amount,
        )


@transaction.atomic
def register_cash_payment(
    *, student_id, amount, allocations, received_by, received_at=None, reference=""
):
    amount = _to_decimal(amount)
    if amount <= 0:
        raise ValidationError(_("El importe recibido debe ser mayor que cero."))
    Student.objects.get(pk=student_id)
    locked_allocations = _lock_and_validate_allocations(student_id, amount, allocations)

    payment = Payment(
        student_id=student_id,
        amount=amount,
        currency=ARS,
        method=Payment.Method.CASH,
        received_at=received_at or timezone.now(),
        confirmed_by=received_by,
        reference=reference,
    )
    payment.save(_from_payment_service=True)
    _create_allocations(payment, locked_allocations)
    return payment


@transaction.atomic
def register_transfer_intent(*, student_id, amount, created_by, reference=""):
    intent = PaymentIntent(
        student_id=student_id,
        method=PaymentIntent.Method.BANK_TRANSFER,
        amount=_to_decimal(amount),
        currency=ARS,
        status=PaymentIntent.Status.PENDING,
        reference=reference,
        created_by=created_by,
    )
    intent.save()
    return intent


@transaction.atomic
def confirm_transfer(*, intent_id, allocations, confirmed_by, received_at=None):
    intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
    if intent.status == PaymentIntent.Status.CONFIRMED:
        try:
            return intent.payment
        except Payment.DoesNotExist as exc:
            raise ValidationError(
                _("La transferencia figura confirmada pero no tiene un pago asociado.")
            ) from exc
    if intent.status == PaymentIntent.Status.REJECTED:
        raise ValidationError(_("Una transferencia rechazada no se puede confirmar."))
    if intent.method != PaymentIntent.Method.BANK_TRANSFER:
        raise ValidationError(
            _("Este medio de pago todavía no admite confirmación manual.")
        )

    locked_allocations = _lock_and_validate_allocations(
        intent.student_id, intent.amount, allocations
    )
    payment = Payment(
        student_id=intent.student_id,
        amount=intent.amount,
        currency=intent.currency,
        method=Payment.Method.BANK_TRANSFER,
        received_at=received_at or timezone.now(),
        confirmed_by=confirmed_by,
        reference=intent.reference,
        intent=intent,
    )
    payment.save(_from_payment_service=True)
    _create_allocations(payment, locked_allocations)

    intent.status = PaymentIntent.Status.CONFIRMED
    intent.decided_at = timezone.now()
    intent.decided_by = confirmed_by
    intent.save(update_fields=("status", "decided_at", "decided_by"))
    return payment


@transaction.atomic
def reject_transfer(*, intent_id, rejected_by):
    intent = PaymentIntent.objects.select_for_update().get(pk=intent_id)
    if intent.status == PaymentIntent.Status.REJECTED:
        return intent
    if intent.status == PaymentIntent.Status.CONFIRMED:
        raise ValidationError(_("Un pago confirmado no se puede rechazar."))

    intent.status = PaymentIntent.Status.REJECTED
    intent.decided_at = timezone.now()
    intent.decided_by = rejected_by
    intent.save(update_fields=("status", "decided_at", "decided_by"))
    return intent
