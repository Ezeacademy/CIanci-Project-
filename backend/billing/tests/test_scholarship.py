import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import (
    SCHOLARSHIP_PERCENTAGES,
    DisciplinePrice,
    MonthlyCharge,
    Scholarship,
)


class ScholarshipModelTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.jazz = Discipline.objects.create(name="Jazz")
        self.classic = Discipline.objects.create(name="Clásico")

    def create_scholarship(self, **overrides):
        values = {
            "student": self.student,
            "discipline": self.jazz,
            "percentage": 50,
            "start_month": date(2026, 10, 1),
        }
        values.update(overrides)
        return Scholarship.objects.create(**values)

    def test_only_five_percent_increments_are_allowed(self):
        self.assertEqual(SCHOLARSHIP_PERCENTAGES, tuple(range(5, 101, 5)))
        with self.assertRaises(ValidationError):
            self.create_scholarship(percentage=7)

    def test_months_must_start_on_first_and_end_cannot_precede_start(self):
        with self.assertRaises(ValidationError):
            self.create_scholarship(start_month=date(2026, 10, 2))
        with self.assertRaises(ValidationError):
            self.create_scholarship(
                start_month=date(2026, 11, 1),
                end_month=date(2026, 10, 1),
            )

    def test_open_ended_scholarships_and_other_disciplines_are_valid(self):
        ongoing_scholarship = self.create_scholarship(end_month=None)
        other_discipline_scholarship = self.create_scholarship(
            discipline=self.classic,
            start_month=date(2026, 10, 1),
        )

        self.assertIsNone(ongoing_scholarship.end_month)
        self.assertEqual(other_discipline_scholarship.discipline, self.classic)

    def test_non_overlapping_inclusive_periods_are_allowed(self):
        self.create_scholarship(end_month=date(2026, 10, 1))

        following_scholarship = self.create_scholarship(
            percentage=75,
            start_month=date(2026, 11, 1),
            end_month=None,
        )

        self.assertEqual(following_scholarship.start_month, date(2026, 11, 1))

    def test_overlap_is_rejected_by_validation_and_postgresql_constraint(self):
        self.create_scholarship(end_month=date(2026, 12, 1))
        overlapping_scholarship = Scholarship(
            student=self.student,
            discipline=self.jazz,
            percentage=25,
            start_month=date(2026, 12, 1),
            end_month=None,
        )

        with self.assertRaises(ValidationError):
            overlapping_scholarship.full_clean()

        with self.assertRaises(IntegrityError), transaction.atomic():
            Scholarship.objects.bulk_create([overlapping_scholarship])

    def test_postgresql_rejects_invalid_percentage_and_non_month_dates(self):
        invalid_percentage = Scholarship(
            student=self.student,
            discipline=self.jazz,
            percentage=7,
            start_month=date(2026, 10, 1),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Scholarship.objects.bulk_create([invalid_percentage])

        invalid_month_start = Scholarship(
            student=self.student,
            discipline=self.jazz,
            percentage=50,
            start_month=date(2026, 10, 15),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Scholarship.objects.bulk_create([invalid_month_start])

    def test_postgresql_rejects_discount_that_does_not_match_the_percentage(self):
        enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 10, 1),
        )
        discipline_price = DisciplinePrice.objects.create(
            discipline=self.jazz,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        invalid_charge = MonthlyCharge(
            student=self.student,
            discipline=self.jazz,
            enrollment=enrollment,
            period=date(2026, 10, 1),
            price_applied=discipline_price,
            base_amount=Decimal("30000.00"),
            scholarship_percentage=50,
            discount_amount=Decimal("14000.00"),
            amount=Decimal("16000.00"),
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            MonthlyCharge.objects.bulk_create([invalid_charge])

    def test_overlapping_periods_for_another_student_are_allowed(self):
        self.create_scholarship(end_month=None)
        other_student = Student.objects.create(
            first_name="Sofía", last_name="Manzo"
        )

        other_student_scholarship = self.create_scholarship(student=other_student)

        self.assertEqual(other_student_scholarship.student, other_student)


class ScholarshipCalculationTests(TestCase):
    def test_discount_uses_decimal_half_up_cent_rounding(self):
        from billing.models import calculate_scholarship_discount

        self.assertEqual(
            calculate_scholarship_discount(
                base_amount=Decimal("30000.00"), percentage=5
            ),
            Decimal("1500.00"),
        )
        self.assertEqual(
            calculate_scholarship_discount(
                base_amount=Decimal("0.10"), percentage=5
            ),
            Decimal("0.01"),
        )


class ConcurrentScholarshipCreationTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_overlapping_scholarships_cannot_both_be_saved(self):
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        discipline = Discipline.objects.create(name="Jazz")
        creation_barrier = threading.Barrier(2)

        def create_scholarship(percentage):
            close_old_connections()
            try:
                creation_barrier.wait(timeout=10)
                Scholarship.objects.create(
                    student=student,
                    discipline=discipline,
                    percentage=percentage,
                    start_month=date(2026, 10, 1),
                    end_month=date(2026, 12, 1),
                )
                return "created"
            except ValidationError:
                return "overlap"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create_scholarship, (25, 50)))

        self.assertCountEqual(results, ["created", "overlap"])
        self.assertEqual(Scholarship.objects.count(), 1)
