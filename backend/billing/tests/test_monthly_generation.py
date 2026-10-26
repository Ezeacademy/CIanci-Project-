import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge


class MonthlyChargeGenerationTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.jazz = Discipline.objects.create(name="Jazz")

    def add_price(self, discipline, amount, effective_month):
        return DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal(amount),
            effective_month=effective_month,
        )

    def run_generation(self, period="2026-10", stdout=None, stderr=None):
        return call_command(
            "generate_monthly_charges",
            period=period,
            stdout=stdout or StringIO(),
            stderr=stderr or StringIO(),
        )

    def test_midmonth_start_and_end_are_charged_for_the_full_month(self):
        jazz_enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 15),
            ended_at=date(2026, 10, 20),
        )
        classic = Discipline.objects.create(name="Clásico")
        classic_enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=classic,
            enrolled_at=date(2026, 9, 1),
            ended_at=date(2026, 10, 10),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        self.add_price(classic, "25000.00", date(2026, 9, 1))

        output = StringIO()
        self.run_generation(stdout=output)

        charges = list(MonthlyCharge.objects.order_by("discipline_id"))
        self.assertEqual(len(charges), 2)
        self.assertEqual(
            {charge.discipline_id: charge.amount for charge in charges},
            {
                self.jazz.pk: Decimal("30000.00"),
                classic.pk: Decimal("25000.00"),
            },
        )
        self.assertEqual(
            {charge.enrollment_id for charge in charges},
            {jazz_enrollment.pk, classic_enrollment.pk},
        )
        self.assertTrue(all(charge.period == date(2026, 10, 1) for charge in charges))
        self.assertIn("creados: 2", output.getvalue())

    def test_enrollment_outside_period_does_not_generate_a_charge(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 11, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))

        self.run_generation()

        self.assertFalse(MonthlyCharge.objects.exists())

    def test_price_in_effect_for_period_is_used_and_rerun_is_immutable(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 9, 1),
        )
        october_price = self.add_price(self.jazz, "30000.00", date(2026, 9, 1))
        self.add_price(self.jazz, "40000.00", date(2026, 11, 1))

        first_output = StringIO()
        self.run_generation(stdout=first_output)
        charge = MonthlyCharge.objects.get(period=date(2026, 10, 1))
        self.assertEqual(charge.price_applied_id, october_price.pk)
        self.assertEqual(charge.amount, Decimal("30000.00"))

        rerun_output = StringIO()
        self.run_generation(stdout=rerun_output)
        charge.refresh_from_db()
        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(charge.amount, Decimal("30000.00"))
        self.assertIn("existentes: 1", rerun_output.getvalue())

        self.run_generation(period="2026-11")
        november_charge = MonthlyCharge.objects.get(period=date(2026, 11, 1))
        self.assertEqual(november_charge.amount, Decimal("40000.00"))

    def test_reenrollment_in_same_month_creates_only_one_charge(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 9, 1),
            ended_at=date(2026, 10, 10),
        )
        renewed = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 11),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))

        self.run_generation()

        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(MonthlyCharge.objects.get().enrollment_id, renewed.pk)

    def test_missing_price_is_reported_and_does_not_create_zero_charge(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        stderr = StringIO()
        stdout = StringIO()

        with self.assertRaises(CommandError):
            self.run_generation(stdout=stdout, stderr=stderr)

        self.assertIn("Sin tarifa aplicable", stderr.getvalue())
        self.assertIn("omitidos: 1", stdout.getvalue())
        self.assertFalse(MonthlyCharge.objects.exists())

    def test_invalid_period_format_is_rejected(self):
        with self.assertRaises(CommandError):
            self.run_generation(period="2026-13")
        with self.assertRaises(CommandError):
            self.run_generation(period="2026-1")

    def test_retroactive_baja_cannot_contradict_charge_but_midmonth_baja_is_valid(
        self,
    ):
        enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 9, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        self.run_generation()

        enrollment.ended_at = date(2026, 9, 30)
        with self.assertRaises(ValidationError):
            enrollment.save()

        enrollment.refresh_from_db()
        enrollment.ended_at = date(2026, 10, 15)
        enrollment.save()
        self.assertEqual(enrollment.ended_at, date(2026, 10, 15))
        self.assertEqual(MonthlyCharge.objects.count(), 1)


class ConcurrentMonthlyChargeGenerationTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_runs_create_only_one_charge(self):
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        discipline = Discipline.objects.create(name="Jazz")
        Enrollment.objects.create(
            student=student,
            discipline=discipline,
            enrolled_at=date(2026, 10, 1),
        )
        DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        barrier = threading.Barrier(2)

        def generate():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                output = StringIO()
                call_command(
                    "generate_monthly_charges",
                    period="2026-10",
                    stdout=output,
                    stderr=StringIO(),
                )
                return output.getvalue()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outputs = list(executor.map(lambda _: generate(), range(2)))

        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(sum("creados: 1" in output for output in outputs), 1)
        self.assertEqual(sum("existentes: 1" in output for output in outputs), 1)
