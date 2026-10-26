from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge


class BillingModelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "billing-admin@example.com", "Safe-password-92!"
        )
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrolled_at=date(2026, 10, 15),
        )
        self.price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
            created_by=self.user,
        )

    def create_charge(self, **overrides):
        values = {
            "student": self.student,
            "discipline": self.discipline,
            "enrollment": self.enrollment,
            "period": date(2026, 10, 1),
            "price_applied": self.price,
            "amount": self.price.amount,
            "currency": "ARS",
        }
        values.update(overrides)
        return MonthlyCharge.objects.create(**values)

    def test_charge_snapshots_monthly_price_and_protects_history(self):
        charge = self.create_charge()
        self.assertEqual(charge.amount, Decimal("30000.00"))

        next_price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("40000.00"),
            effective_month=date(2026, 11, 1),
            created_by=self.user,
        )
        next_price.refresh_from_db()
        self.assertEqual(charge.amount, Decimal("30000.00"))

        self.price.amount = Decimal("35000.00")
        with self.assertRaises(ValidationError):
            self.price.save()
        with self.assertRaises(ValidationError):
            charge.save()
        with self.assertRaises(ValidationError):
            charge.delete()

    def test_database_rejects_duplicate_price_month_and_duplicate_charge(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            DisciplinePrice.objects.bulk_create(
                [
                    DisciplinePrice(
                        discipline=self.discipline,
                        amount=Decimal("31000.00"),
                        effective_month=date(2026, 10, 1),
                    )
                ]
            )

        first = MonthlyCharge(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 10, 1),
            price_applied=self.price,
            amount=self.price.amount,
        )
        duplicate = MonthlyCharge(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 10, 1),
            price_applied=self.price,
            amount=self.price.amount,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MonthlyCharge.objects.bulk_create([first, duplicate])

    def test_database_rejects_nonpositive_amounts_and_non_month_periods(self):
        invalid_price = DisciplinePrice(
            discipline=self.discipline,
            amount=Decimal("0.00"),
            effective_month=date(2026, 10, 1),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            DisciplinePrice.objects.bulk_create([invalid_price])

        invalid_charge = MonthlyCharge(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 10, 15),
            price_applied=self.price,
            amount=Decimal("-1.00"),
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            MonthlyCharge.objects.bulk_create([invalid_charge])

    def test_charge_must_match_enrollment_student_discipline_and_price(self):
        other_student = Student.objects.create(first_name="Ana", last_name="Cianci")
        with self.assertRaises(ValidationError):
            self.create_charge(student=other_student)

        other_discipline = Discipline.objects.create(name="Clásico")
        with self.assertRaises(ValidationError):
            self.create_charge(discipline=other_discipline)

        with self.assertRaises(ValidationError):
            self.create_charge(amount=Decimal("29000.00"))

    def test_enrollment_without_charges_can_be_corrected_or_deleted(self):
        corrected_student = Student.objects.create(first_name="Luz", last_name="Cianci")
        self.enrollment.student = corrected_student
        self.enrollment.enrolled_at = date(2026, 10, 1)
        self.enrollment.save()
        self.assertEqual(self.enrollment.student_id, corrected_student.pk)

        self.enrollment.delete()
        self.assertFalse(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_enrollment_with_charge_keeps_history_and_protects_economic_reference(self):
        charge = self.create_charge()
        original_start = self.enrollment.enrolled_at
        self.enrollment.ended_at = date(2026, 10, 31)
        self.enrollment.save(update_fields=("ended_at",))

        self.enrollment.enrolled_at = date(2026, 10, 1)
        with self.assertRaises(ValidationError):
            self.enrollment.save()
        with self.assertRaises(ProtectedError):
            self.enrollment.delete()

        self.enrollment.refresh_from_db()
        charge.refresh_from_db()
        self.assertEqual(self.enrollment.enrolled_at, original_start)
        self.assertEqual(self.enrollment.ended_at, date(2026, 10, 31))
        self.assertEqual(charge.amount, Decimal("30000.00"))
