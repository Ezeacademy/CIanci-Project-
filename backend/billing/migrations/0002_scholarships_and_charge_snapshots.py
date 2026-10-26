from decimal import Decimal

import django.contrib.postgres.constraints
import django.contrib.postgres.fields.ranges
import django.db.models.deletion
from django.conf import settings
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models
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

SCHOLARSHIP_PERCENTAGES = tuple(range(5, 101, 5))


def copy_existing_charge_amounts(apps, schema_editor):
    monthly_charge_model = apps.get_model("billing", "MonthlyCharge")
    monthly_charge_model.objects.using(schema_editor.connection.alias).update(
        base_amount=F("amount"), discount_amount=Decimal("0.00")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.CreateModel(
            name="Scholarship",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "percentage",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (value, f"{value} %")
                            for value in SCHOLARSHIP_PERCENTAGES
                        ],
                        verbose_name="Porcentaje de beca",
                    ),
                ),
                ("start_month", models.DateField(verbose_name="Mes de inicio")),
                (
                    "end_month",
                    models.DateField(
                        blank=True,
                        help_text=(
                            "Dejá vacío si continúa vigente. Las mensualidades ya "
                            "emitidas no se modificarán automáticamente."
                        ),
                        null=True,
                        verbose_name="Mes de finalización",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Fecha de creación"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_scholarships",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Registrada por",
                    ),
                ),
                (
                    "discipline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scholarships",
                        to="academy.discipline",
                        verbose_name="Disciplina",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scholarships",
                        to="academy.student",
                        verbose_name="Alumno",
                    ),
                ),
            ],
            options={
                "verbose_name": "Beca",
                "verbose_name_plural": "Becas",
                "ordering": (
                    "student__last_name",
                    "student__first_name",
                    "start_month",
                ),
            },
        ),
        migrations.AddField(
            model_name="monthlycharge",
            name="base_amount",
            field=models.DecimalField(
                decimal_places=2, max_digits=12, null=True, verbose_name="Precio base"
            ),
        ),
        migrations.AddField(
            model_name="monthlycharge",
            name="scholarship_percentage",
            field=models.PositiveSmallIntegerField(
                blank=True,
                choices=[(value, f"{value} %") for value in SCHOLARSHIP_PERCENTAGES],
                null=True,
                verbose_name="Beca aplicada",
            ),
        ),
        migrations.AddField(
            model_name="monthlycharge",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0.00"),
                max_digits=12,
                verbose_name="Descuento por beca",
            ),
        ),
        migrations.AlterField(
            model_name="monthlycharge",
            name="amount",
            field=models.DecimalField(
                decimal_places=2, max_digits=12, verbose_name="Total a pagar"
            ),
        ),
        migrations.RunPython(copy_existing_charge_amounts, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="monthlycharge",
            name="base_amount",
            field=models.DecimalField(
                decimal_places=2, max_digits=12, verbose_name="Precio base"
            ),
        ),
        migrations.RemoveConstraint(
            model_name="monthlycharge", name="billing_charge_amount_positive"
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
                condition=Q(base_amount__gt=0),
                name="billing_charge_base_amount_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
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
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
                condition=Q(discount_amount__gte=0),
                name="billing_charge_discount_nonnegative",
            ),
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
                condition=Q(amount__gte=0), name="billing_charge_amount_nonnegative"
            ),
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
                condition=Q(amount=F("base_amount") - F("discount_amount")),
                name="billing_charge_amount_matches_discount",
            ),
        ),
        migrations.AddConstraint(
            model_name="monthlycharge",
            constraint=models.CheckConstraint(
                condition=(
                    Q(scholarship_percentage__isnull=True, discount_amount=0)
                    | Q(scholarship_percentage__in=SCHOLARSHIP_PERCENTAGES)
                ),
                name="billing_charge_scholarship_snapshot_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="scholarship",
            constraint=models.CheckConstraint(
                condition=Q(percentage__in=SCHOLARSHIP_PERCENTAGES),
                name="billing_scholarship_percentage_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="scholarship",
            constraint=models.CheckConstraint(
                condition=Q(start_month__day=1),
                name="billing_scholarship_start_month_first_day",
            ),
        ),
        migrations.AddConstraint(
            model_name="scholarship",
            constraint=models.CheckConstraint(
                condition=Q(end_month__isnull=True) | Q(end_month__day=1),
                name="billing_scholarship_end_month_first_day",
            ),
        ),
        migrations.AddConstraint(
            model_name="scholarship",
            constraint=models.CheckConstraint(
                condition=Q(end_month__isnull=True)
                | Q(end_month__gte=F("start_month")),
                name="billing_scholarship_end_not_before_start",
            ),
        ),
        migrations.AddConstraint(
            model_name="scholarship",
            constraint=django.contrib.postgres.constraints.ExclusionConstraint(
                expressions=(
                    ("student", "="),
                    ("discipline", "="),
                    (
                        Func(
                            F("start_month"),
                            F("end_month"),
                            Value("[]"),
                            function="daterange",
                            output_field=django.contrib.postgres.fields.ranges.DateRangeField(),
                        ),
                        "&&",
                    ),
                ),
                name="billing_scholarship_period_no_overlap",
            ),
        ),
    ]
