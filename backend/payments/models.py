from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from academy.models import Student
from billing.models import MonthlyCharge

ARS = "ARS"


class PaymentIntent(models.Model):
    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", _("Transferencia bancaria")
        MERCADO_PAGO = "mercado_pago", _("Mercado Pago")

    class Status(models.TextChoices):
        PENDING = "pending", _("Pendiente de verificación")
        CONFIRMED = "confirmed", _("Confirmada")
        REJECTED = "rejected", _("Rechazada")

    student = models.ForeignKey(
        Student,
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="payment_intents",
    )
    method = models.CharField(
        _("Medio de pago"),
        max_length=20,
        choices=Method.choices,
        default=Method.BANK_TRANSFER,
    )
    amount = models.DecimalField(
        _("Importe informado"), max_digits=12, decimal_places=2
    )
    currency = models.CharField(
        _("Moneda"), max_length=3, choices=((ARS, ARS),), default=ARS
    )
    status = models.CharField(
        _("Estado"),
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reference = models.CharField(
        _("Referencia o comprobante"), max_length=255, blank=True
    )
    created_at = models.DateTimeField(_("Fecha informada"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Informada por"),
        on_delete=models.PROTECT,
        related_name="created_payment_intents",
    )
    decided_at = models.DateTimeField(_("Fecha de resolución"), null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Resuelta por"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="decided_payment_intents",
    )

    class Meta:
        verbose_name = _("Transferencia informada")
        verbose_name_plural = _("Transferencias informadas")
        ordering = ("status", "-created_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_intent_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(currency=ARS), name="payments_intent_currency_ars"
            ),
            models.CheckConstraint(
                condition=Q(method__in=("bank_transfer", "mercado_pago")),
                name="payments_intent_method_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=("pending", "confirmed", "rejected")),
                name="payments_intent_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="pending",
                        decided_at__isnull=True,
                        decided_by__isnull=True,
                    )
                    | Q(
                        status__in=("confirmed", "rejected"),
                        decided_at__isnull=False,
                        decided_by__isnull=False,
                    )
                ),
                name="payments_intent_decision_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        if self._state.adding and (
            self.status != self.Status.PENDING
            or self.decided_at is not None
            or self.decided_by_id is not None
        ):
            raise ValidationError(_("Una transferencia nueva debe quedar pendiente."))

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                previous = PaymentIntent.objects.select_for_update().get(pk=self.pk)
                immutable_fields = (
                    "student_id",
                    "method",
                    "amount",
                    "currency",
                    "reference",
                    "created_by_id",
                    "created_at",
                )
                if any(
                    getattr(self, field) != getattr(previous, field)
                    for field in immutable_fields
                ):
                    raise ValidationError(
                        _(
                            "Los datos informados de una transferencia no se pueden "
                            "editar."
                        )
                    )
                if previous.status != self.Status.PENDING:
                    raise ValidationError(
                        _("Una transferencia resuelta no se puede volver a modificar.")
                    )
                if self.status not in (self.Status.CONFIRMED, self.Status.REJECTED):
                    raise ValidationError(
                        _("La transferencia solo puede confirmarse o rechazarse.")
                    )
                if self.status == self.Status.CONFIRMED:
                    payment = Payment.objects.filter(intent_id=self.pk).first()
                    if (
                        payment is None
                        or payment.allocations.aggregate(total=Sum("amount"))["total"]
                        != self.amount
                    ):
                        raise ValidationError(
                            _(
                                "Para confirmar, la transferencia debe tener un pago "
                                "con asignaciones por el importe completo."
                            )
                        )
                elif Payment.objects.filter(intent_id=self.pk).exists():
                    raise ValidationError(
                        _(
                            "Una transferencia con un pago asociado no se puede "
                            "rechazar."
                        )
                    )
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Las transferencias informadas no se pueden eliminar."))

    def __str__(self):
        return f"{self.student} — {self.amount} {self.currency} ({self.status})"


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "cash", _("Efectivo")
        BANK_TRANSFER = "bank_transfer", _("Transferencia bancaria")
        MERCADO_PAGO = "mercado_pago", _("Mercado Pago")

    student = models.ForeignKey(
        Student,
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(_("Importe recibido"), max_digits=12, decimal_places=2)
    currency = models.CharField(
        _("Moneda"), max_length=3, choices=((ARS, ARS),), default=ARS
    )
    method = models.CharField(_("Medio de pago"), max_length=20, choices=Method.choices)
    received_at = models.DateTimeField(_("Fecha de recepción"), default=timezone.now)
    created_at = models.DateTimeField(_("Fecha de registro"), auto_now_add=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Registrado o confirmado por"),
        on_delete=models.PROTECT,
        related_name="confirmed_payments",
    )
    reference = models.CharField(_("Referencia"), max_length=255, blank=True)
    intent = models.OneToOneField(
        PaymentIntent,
        verbose_name=_("Transferencia informada"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="payment",
    )

    class Meta:
        verbose_name = _("Pago confirmado")
        verbose_name_plural = _("Pagos confirmados")
        ordering = ("-received_at", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(currency=ARS), name="payments_currency_ars"
            ),
            models.CheckConstraint(
                condition=Q(method__in=("cash", "bank_transfer", "mercado_pago")),
                name="payments_method_valid",
            ),
        ]

    def clean(self):
        super().clean()
        if self.intent_id:
            intent = PaymentIntent.objects.get(pk=self.intent_id)
            if intent.status != PaymentIntent.Status.PENDING:
                raise ValidationError(
                    _(
                        "Solo se puede crear el pago al confirmar una transferencia "
                        "pendiente."
                    )
                )
            if (
                self.student_id != intent.student_id
                or self.amount != intent.amount
                or self.currency != intent.currency
                or self.method != intent.method
            ):
                raise ValidationError(
                    _(
                        "El pago debe coincidir con los datos de la transferencia "
                        "informada."
                    )
                )

    def save(self, *args, **kwargs):
        created_by_service = kwargs.pop("_from_payment_service", False)
        if not self._state.adding:
            raise ValidationError(_("Los pagos confirmados no se pueden modificar."))
        if not created_by_service:
            raise ValidationError(
                _(
                    "Los pagos confirmados solo se registran mediante los servicios "
                    "de pagos."
                )
            )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Los pagos confirmados no se pueden eliminar."))

    @property
    def allocated_amount(self):
        return self.allocations.aggregate(total=Sum("amount"))["total"] or Decimal(
            "0.00"
        )

    @property
    def unallocated_amount(self):
        return self.amount - self.allocated_amount

    def __str__(self):
        return f"{self.student} — {self.amount} {self.currency}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(
        Payment,
        verbose_name=_("Pago"),
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    charge = models.ForeignKey(
        MonthlyCharge,
        verbose_name=_("Cargo mensual"),
        on_delete=models.PROTECT,
        related_name="payment_allocations",
    )
    amount = models.DecimalField(_("Importe asignado"), max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = _("Asignación de pago")
        verbose_name_plural = _("Asignaciones de pagos")
        ordering = ("pk",)
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_allocation_amount_positive"
            ),
            models.UniqueConstraint(
                fields=("payment", "charge"), name="payments_allocation_pair_unique"
            ),
        ]

    def clean(self):
        super().clean()
        if self.payment_id and self.charge_id:
            payment = Payment.objects.get(pk=self.payment_id)
            charge = MonthlyCharge.objects.get(pk=self.charge_id)
            if payment.student_id != charge.student_id:
                raise ValidationError(
                    {"charge": _("El cargo debe pertenecer al mismo alumno del pago.")}
                )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(
                _("Las asignaciones de pagos no se pueden modificar.")
            )

        with transaction.atomic():
            self.full_clean()
            student_id = Payment.objects.values_list("student_id", flat=True).get(
                pk=self.payment_id
            )
            Student.objects.select_for_update().get(pk=student_id)
            payment = Payment.objects.select_for_update().get(pk=self.payment_id)
            charge = MonthlyCharge.objects.select_for_update().get(pk=self.charge_id)
            if payment.student_id != charge.student_id:
                raise ValidationError(
                    {"charge": _("El cargo debe pertenecer al mismo alumno del pago.")}
                )

            already_in_payment = payment.allocations.aggregate(total=Sum("amount"))[
                "total"
            ] or Decimal("0.00")
            if already_in_payment + self.amount > payment.amount:
                raise ValidationError(
                    {"amount": _("La asignación supera el importe del pago.")}
                )

            from billing.queries import charges_with_economic_totals

            current_charge = charges_with_economic_totals().get(pk=charge.pk)
            if self.amount > current_charge.outstanding:
                raise ValidationError(
                    {"amount": _("La asignación supera el saldo pendiente del cargo.")}
                )

            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Las asignaciones de pagos no se pueden eliminar."))

    def __str__(self):
        return f"{self.charge} — {self.amount}"


class CreditRelease(models.Model):
    adjustment = models.ForeignKey(
        "billing.ChargeAdjustment",
        on_delete=models.PROTECT,
        related_name="credit_releases",
        verbose_name=_("Ajuste de origen"),
    )
    allocation = models.ForeignKey(
        PaymentAllocation,
        on_delete=models.PROTECT,
        related_name="credit_releases",
        verbose_name=_("Asignación de origen"),
    )
    amount = models.DecimalField(
        _("Saldo a favor liberado"), max_digits=12, decimal_places=2
    )
    created_at = models.DateTimeField(_("Fecha"), auto_now_add=True)

    class Meta:
        ordering = ("created_at", "pk")
        verbose_name = _("Saldo a favor")
        verbose_name_plural = _("Saldos a favor")
        default_permissions = ("view",)
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_release_amount_positive"
            ),
            models.UniqueConstraint(
                fields=("adjustment", "allocation"),
                name="payments_release_adjustment_allocation_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.adjustment_id and self.allocation_id:
            if self.adjustment.charge_id != self.allocation.charge_id:
                raise ValidationError(
                    _("La asignación debe pertenecer a la mensualidad ajustada.")
                )
            if self.amount is not None and self.amount > self.allocation.amount:
                raise ValidationError(_("El crédito supera la asignación de origen."))

    def save(self, *args, **kwargs):
        """Append a release only within the locked adjustment transaction."""
        if not self._state.adding or not kwargs.pop("_from_adjustment_service", False):
            raise ValidationError(
                _("Los saldos a favor se generan al ajustar mensualidades.")
            )
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            _("Los movimientos de saldo a favor no se pueden eliminar.")
        )
