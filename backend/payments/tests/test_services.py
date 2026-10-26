from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import TestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import Payment, PaymentAllocation, PaymentIntent
from payments.services import (
    confirm_transfer,
    register_cash_payment,
    register_transfer_intent,
    reject_transfer,
)


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "cashier@example.com", "Safe-password-92!"
        )
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.other_student = Student.objects.create(
            first_name="Sofía", last_name="Cianci"
        )
        self.jazz = Discipline.objects.create(name="Jazz")
        self.classic = Discipline.objects.create(name="Clásico")
        self.jazz_charge = self.create_charge(
            student=self.student,
            discipline=self.jazz,
            amount="30000.00",
        )
        self.classic_charge = self.create_charge(
            student=self.student,
            discipline=self.classic,
            amount="25000.00",
        )
        self.other_charge = self.create_charge(
            student=self.other_student,
            discipline=self.jazz,
            amount="10000.00",
        )

    def create_charge(self, *, student, discipline, amount):
        enrollment = Enrollment.objects.create(
            student=student,
            discipline=discipline,
            enrolled_at=date(2026, 9, 1),
        )
        price, _ = DisciplinePrice.objects.get_or_create(
            discipline=discipline,
            effective_month=date(2026, 9, 1),
            defaults={"amount": Decimal(amount)},
        )
        return MonthlyCharge.objects.create(
            student=student,
            discipline=discipline,
            enrollment=enrollment,
            period=date(2026, 9, 1),
            price_applied=price,
            amount=price.amount,
        )

    def test_cash_payment_is_confirmed_and_partial_payments_reduce_balance(self):
        first = register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("20000.00"),
            allocations=[(self.jazz_charge.pk, Decimal("20000.00"))],
            received_by=self.user,
        )
        self.assertEqual(first.method, Payment.Method.CASH)
        self.assertEqual(first.allocated_amount, Decimal("20000.00"))
        self.assertEqual(
            self.jazz_charge.amount
            - self.jazz_charge.payment_allocations.aggregate(total=Sum("amount"))[
                "total"
            ],
            Decimal("10000.00"),
        )

        second = register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("35000.00"),
            allocations=[
                (self.jazz_charge.pk, Decimal("10000.00")),
                (self.classic_charge.pk, Decimal("25000.00")),
            ],
            received_by=self.user,
        )
        self.assertEqual(second.allocations.count(), 2)
        self.assertEqual(self.jazz_charge.payment_allocations.count(), 2)
        self.assertEqual(self.classic_charge.payment_allocations.count(), 1)
        self.assertEqual(
            self.jazz_charge.payment_allocations.aggregate(total=Sum("amount"))[
                "total"
            ],
            self.jazz_charge.amount,
        )

    def test_transfer_is_pending_until_confirmed_and_confirmation_is_idempotent(self):
        intent = register_transfer_intent(
            student_id=self.student.pk,
            amount=Decimal("55000.00"),
            created_by=self.user,
            reference="Operación informada 123",
        )
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)
        self.assertEqual(Payment.objects.count(), 0)
        self.assertEqual(PaymentAllocation.objects.count(), 0)

        allocations = [
            (self.jazz_charge.pk, Decimal("30000.00")),
            (self.classic_charge.pk, Decimal("25000.00")),
        ]
        payment = confirm_transfer(
            intent_id=intent.pk,
            allocations=allocations,
            confirmed_by=self.user,
        )
        retry = confirm_transfer(
            intent_id=intent.pk,
            allocations=[],
            confirmed_by=self.user,
        )

        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.CONFIRMED)
        self.assertEqual(intent.decided_by, self.user)
        self.assertEqual(payment.pk, retry.pk)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.count(), 2)

    def test_rejected_transfer_cannot_be_confirmed(self):
        intent = register_transfer_intent(
            student_id=self.student.pk,
            amount=Decimal("10000.00"),
            created_by=self.user,
        )
        reject_transfer(intent_id=intent.pk, rejected_by=self.user)

        with self.assertRaises(ValidationError):
            confirm_transfer(
                intent_id=intent.pk,
                allocations=[(self.jazz_charge.pk, Decimal("10000.00"))],
                confirmed_by=self.user,
            )

        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.REJECTED)
        self.assertFalse(Payment.objects.exists())

    def test_transfer_above_available_debt_stays_pending_without_payment(self):
        intent = register_transfer_intent(
            student_id=self.student.pk,
            amount=Decimal("56000.00"),
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            confirm_transfer(
                intent_id=intent.pk,
                allocations=[
                    (self.jazz_charge.pk, Decimal("30000.00")),
                    (self.classic_charge.pk, Decimal("26000.00")),
                ],
                confirmed_by=self.user,
            )

        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.PENDING)
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(PaymentAllocation.objects.exists())

    def test_rejects_overpayment_wrong_student_and_incomplete_allocation_atomically(
        self,
    ):
        with self.assertRaises(ValidationError):
            register_cash_payment(
                student_id=self.student.pk,
                amount=Decimal("31000.00"),
                allocations=[(self.jazz_charge.pk, Decimal("31000.00"))],
                received_by=self.user,
            )
        with self.assertRaises(ValidationError):
            register_cash_payment(
                student_id=self.student.pk,
                amount=Decimal("10000.00"),
                allocations=[(self.other_charge.pk, Decimal("10000.00"))],
                received_by=self.user,
            )
        with self.assertRaises(ValidationError):
            register_cash_payment(
                student_id=self.student.pk,
                amount=Decimal("10000.00"),
                allocations=[(self.jazz_charge.pk, Decimal("9000.00"))],
                received_by=self.user,
            )

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(PaymentAllocation.objects.exists())

    def test_confirmed_payments_and_allocations_are_immutable(self):
        payment = register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("5000.00"),
            allocations=[(self.jazz_charge.pk, Decimal("5000.00"))],
            received_by=self.user,
        )
        payment.amount = Decimal("4000.00")
        with self.assertRaises(ValidationError):
            payment.save()
        with self.assertRaises(ValidationError):
            payment.delete()
        with self.assertRaises(ValidationError):
            payment.allocations.first().delete()

        with self.assertRaises(ValidationError):
            Payment.objects.create(
                student=self.student,
                amount=Decimal("100.00"),
                method=Payment.Method.CASH,
                confirmed_by=self.user,
            )

    def test_failure_after_payment_creation_rolls_back_payment_and_allocations(self):
        with patch(
            "payments.services._create_allocations",
            side_effect=ValidationError("fallo de prueba"),
        ):
            with self.assertRaises(ValidationError):
                register_cash_payment(
                    student_id=self.student.pk,
                    amount=Decimal("5000.00"),
                    allocations=[(self.jazz_charge.pk, Decimal("5000.00"))],
                    received_by=self.user,
                )

        self.assertFalse(Payment.objects.exists())
        self.assertFalse(PaymentAllocation.objects.exists())
