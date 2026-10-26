from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    Q,
    Value,
    When,
)
from django.db.models.functions import Round
from django.utils.translation import gettext_lazy as _

from academy.models import Discipline, Enrollment, Student

ARS = "ARS"
SCHOLARSHIP_PERCENTAGES = tuple(range(5, 101, 5))
CENT = Decimal("0.01")


def is_month_start(value):
    return value.day == 1


def calculate_scholarship_discount(
    *, base_amount: Decimal, percentage: int
) -> Decimal:
    """Calculate a scholarship discount rounded to the nearest cent.

    Half-cent values round away from zero (ROUND_HALF_UP), matching the currency's
    two-decimal precision. The caller must validate the percentage range.
    """
    return (base_amount * Decimal(percentage) / Decimal(100)).quantize(
        CENT, rounding=ROUND_HALF_UP
    )


class Scholarship(models.Model):
    student = models.ForeignKey(
        Student,
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="scholarships",
    )
    discipline = models.ForeignKey(
        Discipline,
        verbose_name=_("Disciplina"),
        on_delete=models.PROTECT,
        related_name="scholarships",
    )
    percentage = models.PositiveSmallIntegerField(
        _("Porcentaje de beca"),
        choices=tuple((value, f"{value} %") for value in SCHOLARSHIP_PERCENTAGES),
    )
    start_month = models.DateField(_("Mes de inicio"))
    end_month = models.DateField(
        _("Mes de finalización"),
        null=True,
        blank=True,
        help_text=_(
            "Dejá vacío si continúa vigente. Las mensualidades ya emitidas no "
            "se modificarán automáticamente."
        ),
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Registrada por"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_scholarships",
    )

    class Meta:
        verbose_name = _("Beca")
        verbose_name_plural = _("Becas")
        ordering = ("student__last_name", "student__first_name", "start_month")
        constraints = [
            models.CheckConstraint(
                condition=Q(percentage__in=SCHOLARSHIP_PERCENTAGES),
                name="billing_scholarship_percentage_valid",
            ),
            models.CheckConstraint(
                condition=Q(start_month__day=1),
                name="billing_scholarship_start_month_first_day",
            ),
            models.CheckConstraint(
                condition=Q(end_month__isnull=True) | Q(end_month__day=1),
                name="billing_scholarship_end_month_first_day",
            ),
            models.CheckConstraint(
                condition=Q(end_month__isnull=True)
                | Q(end_month__gte=F("start_month")),
                name="billing_scholarship_end_not_before_start",
            ),
            ExclusionConstraint(
                name="billing_scholarship_period_no_overlap",
                expressions=(
                    ("student", RangeOperators.EQUAL),
                    ("discipline", RangeOperators.EQUAL),
                    (
                        Func(
                            F("start_month"),
                            F("end_month"),
                            Value("[]"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ),
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.start_month and not is_month_start(self.start_month):
            errors["start_month"] = _("El mes debe comenzar el primer día.")
        if self.end_month and not is_month_start(self.end_month):
            errors["end_month"] = _("El mes debe comenzar el primer día.")
        if self.start_month and self.end_month and self.end_month < self.start_month:
            errors["end_month"] = _(
                "El mes de finalización debe ser igual o posterior al inicio."
            )
        if self.percentage not in SCHOLARSHIP_PERCENTAGES:
            errors["percentage"] = _(
                "Elegí un porcentaje entre 5 % y 100 %, en incrementos de 5 %."
            )
        if self.student_id and self.discipline_id and self.start_month:
            overlapping_scholarships = Scholarship.objects.filter(
                student_id=self.student_id,
                discipline_id=self.discipline_id,
                start_month__lte=self.end_month or date.max,
            ).filter(Q(end_month__isnull=True) | Q(end_month__gte=self.start_month))
            if self.pk:
                overlapping_scholarships = overlapping_scholarships.exclude(
                    pk=self.pk
                )
            if overlapping_scholarships.exists():
                errors["start_month"] = _(
                    "Ya existe una beca para este alumno y disciplina durante "
                    "parte de ese período."
                )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Serialize scholarship changes per student before checking overlaps.

        The PostgreSQL exclusion constraint remains the final protection against
        concurrent inserts; this row lock also makes the admin validation clearer.
        """
        with transaction.atomic():
            Student.objects.select_for_update().get(pk=self.student_id)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student} — {self.discipline} ({self.percentage} %)"


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
        """Save a tariff version without racing charge generation.

        Lock discipline rows before tariff rows so the generator and tariff changes
        observe a consistent order. Moving an unused price locks both disciplines.
        """
        with transaction.atomic():
            previous_discipline_id = None
            if self.pk:
                previous_discipline_id = DisciplinePrice.objects.values_list(
                    "discipline_id", flat=True
                ).get(pk=self.pk)

            locked_discipline_ids = sorted(
                {
                    discipline_id
                    for discipline_id in (self.discipline_id, previous_discipline_id)
                    if discipline_id is not None
                }
            )
            for discipline_id in locked_discipline_ids:
                Discipline.objects.select_for_update().get(pk=discipline_id)

            if self.pk:
                previous = DisciplinePrice.objects.select_for_update().get(pk=self.pk)
                if previous.discipline_id not in locked_discipline_ids:
                    raise ValidationError(
                        _(
                            "La tarifa cambió en otra operación. Actualizá el "
                            "formulario e intentá de nuevo."
                        )
                    )
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
    base_amount = models.DecimalField(
        _("Precio base"), max_digits=12, decimal_places=2
    )
    scholarship_percentage = models.PositiveSmallIntegerField(
        _("Beca aplicada"),
        choices=tuple((value, f"{value} %") for value in SCHOLARSHIP_PERCENTAGES),
        null=True,
        blank=True,
    )
    discount_amount = models.DecimalField(
        _("Descuento por beca"),
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    amount = models.DecimalField(_("Total a pagar"), max_digits=12, decimal_places=2)
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
                condition=Q(base_amount__gt=0),
                name="billing_charge_base_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="billing_charge_discount_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="billing_charge_amount_nonnegative"
            ),
            models.CheckConstraint(
                condition=Q(amount=F("base_amount") - F("discount_amount")),
                name="billing_charge_amount_matches_discount",
            ),
            models.CheckConstraint(
                condition=(
                    Q(scholarship_percentage__isnull=True, discount_amount=0)
                    | Q(scholarship_percentage__in=SCHOLARSHIP_PERCENTAGES)
                ),
                name="billing_charge_scholarship_snapshot_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    discount_amount=Case(
                        When(
                            scholarship_percentage__isnull=True,
                            then=Value(Decimal("0.00")),
                        ),
                        default=Round(
                            ExpressionWrapper(
                                F("base_amount") * F("scholarship_percentage")
                                / Value(Decimal("100.00")),
                                output_field=DecimalField(
                                    max_digits=18, decimal_places=6
                                ),
                            ),
                            precision=2,
                        ),
                        output_field=DecimalField(max_digits=12, decimal_places=2),
                    )
                ),
                name="billing_charge_discount_matches_percentage",
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
            if self.base_amount is not None and self.base_amount != price.amount:
                errors["base_amount"] = _(
                    "El precio base debe coincidir con la tarifa aplicada."
                )
            if self.scholarship_percentage is None:
                if self.discount_amount != Decimal("0.00"):
                    errors["discount_amount"] = _(
                        "No puede haber descuento sin una beca aplicada."
                    )
            else:
                expected_discount = calculate_scholarship_discount(
                    base_amount=self.base_amount or price.amount,
                    percentage=self.scholarship_percentage,
                )
                if self.discount_amount != expected_discount:
                    errors["discount_amount"] = _(
                        "El descuento no coincide con el porcentaje de beca aplicado."
                    )
            if (
                self.base_amount is not None
                and self.discount_amount is not None
                and self.amount is not None
                and self.amount != self.base_amount - self.discount_amount
            ):
                errors["amount"] = _(
                    "El total debe coincidir con el precio base menos el descuento."
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
            if self.base_amount is None:
                self.base_amount = price.amount
            if self.currency is None:
                self.currency = price.currency
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Los cargos emitidos no se pueden eliminar."))

    def __str__(self):
        return f"{self.student} — {self.discipline} — {self.period:%m/%Y}"
