import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from io import StringIO
from time import monotonic, sleep

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge, Scholarship
from billing.services import (
    generate_monthly_charges,
    get_monthly_charge_period_summary,
)
from payments.models import Payment
from payments.services import register_cash_payment


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

    def test_period_summary_counts_candidates_and_missing_discipline_prices(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        classic = Discipline.objects.create(name="Clásico")
        Enrollment.objects.create(
            student=self.student,
            discipline=classic,
            enrolled_at=date(2026, 10, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))

        period_summary = get_monthly_charge_period_summary(
            billing_period=date(2026, 10, 1)
        )

        self.assertEqual(period_summary.student_count, 1)
        self.assertEqual(period_summary.expected_charge_count, 2)
        self.assertEqual(period_summary.existing_charge_count, 0)
        self.assertEqual(period_summary.pending_charge_count, 2)
        self.assertEqual(period_summary.missing_price_disciplines, ("Clásico",))

    def test_generation_service_can_limit_work_to_one_new_enrollment(self):
        jazz_enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        classic = Discipline.objects.create(name="Clásico")
        Enrollment.objects.create(
            student=self.student,
            discipline=classic,
            enrolled_at=date(2026, 10, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        self.add_price(classic, "25000.00", date(2026, 10, 1))

        generation_result = generate_monthly_charges(
            billing_period=date(2026, 10, 1),
            enrollment_ids=(jazz_enrollment.pk,),
        )

        self.assertEqual(generation_result.created, 1)
        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(MonthlyCharge.objects.get().discipline_id, self.jazz.pk)

    def test_regeneration_preserves_confirmed_payment_allocations_on_existing_charge(
        self,
    ):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        october_price = self.add_price(
            self.jazz, "30000.00", date(2026, 10, 1)
        )
        self.run_generation()
        monthly_charge = MonthlyCharge.objects.get()
        payment_operator = get_user_model().objects.create_user(
            "billing-operator@example.com", "Safe-payment-operator-92!"
        )
        confirmed_payment = register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("5000.00"),
            allocations=[(monthly_charge.pk, Decimal("5000.00"))],
            received_by=payment_operator,
        )
        self.add_price(self.jazz, "40000.00", date(2026, 11, 1))

        self.run_generation()

        monthly_charge.refresh_from_db()
        self.assertEqual(monthly_charge.amount, october_price.amount)
        self.assertEqual(
            monthly_charge.payment_allocations.get().amount, Decimal("5000.00")
        )
        self.assertEqual(confirmed_payment.allocations.count(), 1)

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

    def test_scholarship_is_applied_on_inclusive_start_and_end_months(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        Scholarship.objects.create(
            student=self.student,
            discipline=self.jazz,
            percentage=50,
            start_month=date(2026, 11, 1),
            end_month=date(2026, 12, 1),
        )

        self.run_generation(period="2026-10")
        self.run_generation(period="2026-11")
        self.run_generation(period="2026-12")
        self.run_generation(period="2027-01")

        charges_by_period = {
            charge.period: charge for charge in MonthlyCharge.objects.all()
        }
        october_charge = charges_by_period[date(2026, 10, 1)]
        november_charge = charges_by_period[date(2026, 11, 1)]
        december_charge = charges_by_period[date(2026, 12, 1)]
        january_charge = charges_by_period[date(2027, 1, 1)]
        self.assertEqual(october_charge.amount, Decimal("30000.00"))
        for scholarship_charge in (november_charge, december_charge):
            self.assertEqual(scholarship_charge.base_amount, Decimal("30000.00"))
            self.assertEqual(scholarship_charge.scholarship_percentage, 50)
            self.assertEqual(scholarship_charge.discount_amount, Decimal("15000.00"))
            self.assertEqual(scholarship_charge.amount, Decimal("15000.00"))
        self.assertIsNone(january_charge.scholarship_percentage)
        self.assertEqual(january_charge.discount_amount, Decimal("0.00"))
        self.assertEqual(january_charge.amount, Decimal("30000.00"))

    def test_scholarship_without_matching_enrollment_does_not_create_a_charge(self):
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        Scholarship.objects.create(
            student=self.student,
            discipline=self.jazz,
            percentage=100,
            start_month=date(2026, 10, 1),
        )

        generation_result = generate_monthly_charges(billing_period=date(2026, 10, 1))

        self.assertEqual(generation_result.created, 0)
        self.assertFalse(MonthlyCharge.objects.exists())

    def test_one_hundred_percent_scholarship_creates_zero_charge_without_fake_payment(
        self,
    ):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        Scholarship.objects.create(
            student=self.student,
            discipline=self.jazz,
            percentage=100,
            start_month=date(2026, 10, 1),
        )

        self.run_generation()

        monthly_charge = MonthlyCharge.objects.get()
        self.assertEqual(monthly_charge.base_amount, Decimal("30000.00"))
        self.assertEqual(monthly_charge.discount_amount, Decimal("30000.00"))
        self.assertEqual(monthly_charge.amount, Decimal("0.00"))
        self.assertFalse(monthly_charge.payment_allocations.exists())
        self.assertFalse(Payment.objects.exists())

        repeated_result = generate_monthly_charges(billing_period=date(2026, 10, 1))
        monthly_charge.refresh_from_db()
        self.assertEqual(repeated_result.created, 0)
        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(monthly_charge.amount, Decimal("0.00"))

    def test_five_percent_scholarship_rounds_half_cent_up(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        self.add_price(self.jazz, "0.10", date(2026, 10, 1))
        Scholarship.objects.create(
            student=self.student,
            discipline=self.jazz,
            percentage=5,
            start_month=date(2026, 10, 1),
        )

        self.run_generation()

        monthly_charge = MonthlyCharge.objects.get()
        self.assertEqual(monthly_charge.discount_amount, Decimal("0.01"))
        self.assertEqual(monthly_charge.amount, Decimal("0.09"))

    def test_scholarship_snapshot_uses_price_for_each_period_and_keeps_old_charges(
        self,
    ):
        Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        october_price = self.add_price(self.jazz, "30000.00", date(2026, 10, 1))
        november_price = self.add_price(self.jazz, "40000.00", date(2026, 11, 1))
        scholarship = Scholarship.objects.create(
            student=self.student,
            discipline=self.jazz,
            percentage=50,
            start_month=date(2026, 10, 1),
        )

        self.run_generation(period="2026-10")
        october_charge = MonthlyCharge.objects.get(period=date(2026, 10, 1))
        scholarship.end_month = date(2026, 11, 1)
        scholarship.percentage = 25
        scholarship.save()
        self.run_generation(period="2026-11")
        november_charge = MonthlyCharge.objects.get(period=date(2026, 11, 1))

        october_charge.refresh_from_db()
        self.assertEqual(october_charge.price_applied_id, october_price.pk)
        self.assertEqual(october_charge.base_amount, Decimal("30000.00"))
        self.assertEqual(october_charge.scholarship_percentage, 50)
        self.assertEqual(october_charge.discount_amount, Decimal("15000.00"))
        self.assertEqual(october_charge.amount, Decimal("15000.00"))
        self.assertEqual(november_charge.price_applied_id, november_price.pk)
        self.assertEqual(november_charge.base_amount, Decimal("40000.00"))
        self.assertEqual(november_charge.scholarship_percentage, 25)
        self.assertEqual(november_charge.discount_amount, Decimal("10000.00"))
        self.assertEqual(november_charge.amount, Decimal("30000.00"))

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

    def test_generation_waits_for_a_concurrent_applicable_tariff(self):
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
        tariff_transaction_ready = threading.Event()
        allow_tariff_commit = threading.Event()
        generation_started = threading.Event()

        def create_new_tariff():
            close_old_connections()
            try:
                with transaction.atomic():
                    Discipline.objects.select_for_update().get(pk=discipline.pk)
                    DisciplinePrice.objects.create(
                        discipline=discipline,
                        amount=Decimal("40000.00"),
                        effective_month=date(2026, 11, 1),
                    )
                    tariff_transaction_ready.set()
                    if not allow_tariff_commit.wait(timeout=10):
                        raise TimeoutError("No se autorizó el commit de la tarifa.")
            finally:
                close_old_connections()

        def generate_november_charge():
            close_old_connections()
            try:
                generation_started.set()
                return generate_monthly_charges(
                    billing_period=date(2026, 11, 1)
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            tariff_future = executor.submit(create_new_tariff)
            self.assertTrue(tariff_transaction_ready.wait(timeout=5))
            generation_future = executor.submit(generate_november_charge)
            self.assertTrue(generation_started.wait(timeout=5))

            generation_waited_for_tariff = False
            observed_lock_waits = []
            wait_deadline = monotonic() + 5
            while monotonic() < wait_deadline:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT query FROM pg_stat_activity "
                        "WHERE datname = current_database() "
                        "AND pid <> pg_backend_pid() "
                        "AND wait_event_type = 'Lock'"
                    )
                    observed_lock_waits = [row[0] for row in cursor.fetchall()]
                    generation_waited_for_tariff = any(
                        '"academy_discipline"' in query
                        for query in observed_lock_waits
                    )
                if generation_waited_for_tariff:
                    break
                sleep(0.01)

            allow_tariff_commit.set()
            tariff_future.result(timeout=5)
            generation_future.result(timeout=5)

        self.assertTrue(generation_waited_for_tariff, observed_lock_waits)
        monthly_charge = MonthlyCharge.objects.get(period=date(2026, 11, 1))
        self.assertEqual(monthly_charge.amount, Decimal("40000.00"))
