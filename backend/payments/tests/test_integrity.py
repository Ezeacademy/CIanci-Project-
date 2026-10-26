from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import Payment, PaymentAllocation, PaymentIntent
from payments.services import register_cash_payment


class PaymentDatabaseConstraintTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "cashier@example.com", "Safe-password-92!"
        )
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        discipline = Discipline.objects.create(name="Jazz")
        enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=discipline,
            enrolled_at=date(2026, 9, 1),
        )
        price = DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 9, 1),
        )
        self.charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=discipline,
            enrollment=enrollment,
            period=date(2026, 9, 1),
            price_applied=price,
            amount=price.amount,
        )

    def test_postgresql_rejects_nonpositive_intent_and_payment_amounts(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentIntent.objects.bulk_create(
                [
                    PaymentIntent(
                        student=self.student,
                        amount=Decimal("0.00"),
                        created_by=self.user,
                    )
                ]
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.bulk_create(
                [
                    Payment(
                        student=self.student,
                        amount=Decimal("0.00"),
                        method=Payment.Method.CASH,
                        confirmed_by=self.user,
                    )
                ]
            )

    def test_postgresql_rejects_nonpositive_and_duplicate_allocations(self):
        payment = register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("5000.00"),
            allocations=[(self.charge.pk, Decimal("5000.00"))],
            received_by=self.user,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentAllocation.objects.bulk_create(
                [
                    PaymentAllocation(
                        payment=payment,
                        charge=self.charge,
                        amount=Decimal("0.00"),
                    )
                ]
            )

        with self.assertRaises(IntegrityError), transaction.atomic():
            PaymentAllocation.objects.bulk_create(
                [
                    PaymentAllocation(
                        payment=payment,
                        charge=self.charge,
                        amount=Decimal("1.00"),
                    )
                ]
            )
