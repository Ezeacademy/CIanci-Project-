from calendar import monthrange

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from academy.models import Discipline, Enrollment, Student

ARS = "ARS"


def is_month_start(value):
    return value.day == 1


class DisciplinePrice(models.Model):
    discipline = models.ForeignKey(
        Discipline,
        verbose_name=_("Disciplina"),
        on_delete=models.PROTECT,
        related_name="monthly_prices",
    )
    amount = models.DecimalField(_("Importe"), max_digits=12, decimal_places=2)
    currency = models.CharField(
        _("Moneda"), max_length=3, choices=((ARS, ARS),), default=ARS
    )
    effective_month = models.DateField(_("Vigente desde el mes"))
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Creada por"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_discipline_prices",
    )

    class Meta:
        verbose_name = _("Tarifa de disciplina")
        verbose_name_plural = _("Tarifas de disciplinas")
        ordering = ("discipline__name", "-effective_month")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="billing_price_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(currency=ARS), name="billing_price_currency_ars"
            ),
            models.CheckConstraint(
                condition=Q(effective_month__day=1),
                name="billing_price_effective_month_start",
            ),
            models.UniqueConstraint(
                fields=("discipline", "effective_month"),
                name="billing_discipline_price_month_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.effective_month and not is_month_start(self.effective_month):
            raise ValidationError(
                {
                    "effective_month": _(
                        "La vigencia debe comenzar el primer día del mes."
                    )
                }
            )

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.pk:
                previous = DisciplinePrice.objects.select_for_update().get(pk=self.pk)
                has_charges = MonthlyCharge.objects.filter(
                    price_applied_id=self.pk
                ).exists()
                if has_charges and (
                    self.discipline_id != previous.discipline_id
                    or self.amount != previous.amount
                    or self.currency != previous.currency
                    or self.effective_month != previous.effective_month
                ):
                    raise ValidationError(
                        _(
                            "No se puede modificar una tarifa utilizada en cargos "
                            "emitidos."
                        )
                    )
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.discipline} — {self.effective_month:%m/%Y}: "
            f"{self.amount} {self.currency}"
        )


class MonthlyCharge(models.Model):
    student = models.ForeignKey(
        Student,
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="monthly_charges",
    )
    discipline = models.ForeignKey(
        Discipline,
        verbose_name=_("Disciplina"),
        on_delete=models.PROTECT,
        related_name="monthly_charges",
    )
    enrollment = models.ForeignKey(
        Enrollment,
        verbose_name=_("Inscripción de origen"),
        on_delete=models.PROTECT,
        related_name="monthly_charges",
    )
    period = models.DateField(_("Período"))
    price_applied = models.ForeignKey(
        DisciplinePrice,
        verbose_name=_("Tarifa aplicada"),
        on_delete=models.PROTECT,
        related_name="monthly_charges",
    )
    amount = models.DecimalField(_("Importe emitido"), max_digits=12, decimal_places=2)
    currency = models.CharField(
        _("Moneda"), max_length=3, choices=((ARS, ARS),), default=ARS
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)

    class Meta:
        verbose_name = _("Cargo mensual")
        verbose_name_plural = _("Cargos mensuales")
        ordering = ("-period", "student__last_name", "student__first_name")
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="billing_charge_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(currency=ARS), name="billing_charge_currency_ars"
            ),
            models.CheckConstraint(
                condition=Q(period__day=1), name="billing_charge_period_month_start"
            ),
            models.UniqueConstraint(
                fields=("student", "discipline", "period"),
                name="billing_charge_student_discipline_period_unique",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.period and not is_month_start(self.period):
            errors["period"] = _(
                "El período debe ser el primer día de un mes calendario."
            )

        if self.enrollment_id:
            enrollment = Enrollment.objects.select_related("student", "discipline").get(
                pk=self.enrollment_id
            )
            if self.student_id and self.student_id != enrollment.student_id:
                errors["student"] = _(
                    "El alumno debe coincidir con la inscripción de origen."
                )
            if self.discipline_id and self.discipline_id != enrollment.discipline_id:
                errors["discipline"] = _(
                    "La disciplina debe coincidir con la inscripción de origen."
                )
            if self.period:
                last_day = monthrange(self.period.year, self.period.month)[1]
                if enrollment.enrolled_at > self.period.replace(day=last_day) or (
                    enrollment.ended_at and enrollment.ended_at < self.period
                ):
                    errors["enrollment"] = _(
                        "La inscripción no estuvo vigente durante el período indicado."
                    )

        if self.price_applied_id:
            price = DisciplinePrice.objects.get(pk=self.price_applied_id)
            if self.discipline_id and self.discipline_id != price.discipline_id:
                errors["price_applied"] = _(
                    "La tarifa aplicada debe corresponder a la disciplina del cargo."
                )
            if self.period and price.effective_month > self.period:
                errors["price_applied"] = _(
                    "La tarifa todavía no estaba vigente durante el período."
                )
            if self.amount is not None and self.amount != price.amount:
                errors["amount"] = _(
                    "El importe emitido debe coincidir con la tarifa aplicada."
                )
            if self.currency and self.currency != price.currency:
                errors["currency"] = _(
                    "La moneda debe coincidir con la tarifa aplicada."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Los cargos emitidos no se pueden modificar."))

        with transaction.atomic():
            enrollment = Enrollment.objects.select_for_update().get(
                pk=self.enrollment_id
            )
            price = DisciplinePrice.objects.select_for_update().get(
                pk=self.price_applied_id
            )
            if self.student_id is None:
                self.student_id = enrollment.student_id
            if self.discipline_id is None:
                self.discipline_id = enrollment.discipline_id
            if self.amount is None:
                self.amount = price.amount
            if self.currency is None:
                self.currency = price.currency
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Los cargos emitidos no se pueden eliminar."))

    def __str__(self):
        return f"{self.student} — {self.discipline} — {self.period:%m/%Y}"
