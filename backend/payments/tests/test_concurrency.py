import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.db.models import Sum
from django.test import TransactionTestCase

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import Payment, PaymentAllocation, PaymentIntent
from payments.services import confirm_transfer, register_transfer_intent


class ConcurrentPaymentConfirmationTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_transfers_cannot_overpay_same_charge(self):
        User = get_user_model()
        staff = User.objects.create_user("cashier@example.com", "Safe-password-92!")
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        discipline = Discipline.objects.create(name="Jazz")
        enrollment = Enrollment.objects.create(
            student=student,
            discipline=discipline,
            enrolled_at=date(2026, 9, 1),
        )
        price = DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal("10000.00"),
            effective_month=date(2026, 9, 1),
        )
        charge = MonthlyCharge.objects.create(
            student=student,
            discipline=discipline,
            enrollment=enrollment,
            period=date(2026, 9, 1),
            price_applied=price,
            amount=price.amount,
        )
        intents = [
            register_transfer_intent(
                student_id=student.pk,
                amount=Decimal("10000.00"),
                created_by=staff,
            )
            for _ in range(2)
        ]
        barrier = threading.Barrier(2)

        def confirm(intent_id):
            close_old_connections()
            try:
                worker = User.objects.get(pk=staff.pk)
                barrier.wait(timeout=10)
                try:
                    confirm_transfer(
                        intent_id=intent_id,
                        allocations=[(charge.pk, Decimal("10000.00"))],
                        confirmed_by=worker,
                    )
                    return "confirmed"
                except ValidationError:
                    return "pending"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(confirm, [intent.pk for intent in intents]))

        self.assertCountEqual(outcomes, ["confirmed", "pending"])
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(PaymentAllocation.objects.count(), 1)
        self.assertEqual(
            PaymentAllocation.objects.filter(charge=charge).aggregate(
                total=Sum("amount")
            )["total"],
            charge.amount,
        )
        self.assertEqual(
            PaymentIntent.objects.filter(status=PaymentIntent.Status.CONFIRMED).count(),
            1,
        )
