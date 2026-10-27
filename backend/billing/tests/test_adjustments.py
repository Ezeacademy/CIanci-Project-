import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship
from billing.adjustments import confirm_charge_adjustment, preview_charge_adjustment
from billing.models import ChargeAdjustment, DisciplinePrice, MonthlyCharge
from billing.queries import charges_with_economic_totals, students_with_available_credit
from payments.models import CreditRelease, PaymentAllocation
from payments.services import (
    confirm_transfer,
    register_cash_payment,
    register_transfer_intent,
)


class AdjustmentFixtures:
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            "ema@example.com", "password", is_staff=True
        )
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=(
                    "adjust_monthlycharge",
                    "view_monthlycharge",
                    "view_creditrelease",
                )
            )
        )
        self.owner = get_user_model().objects.create_user(
            "student@example.com", "password"
        )
        self.student = Student.objects.create(
            first_name="Ana", last_name="Cianci", user=self.owner
        )
        discipline = Discipline.objects.create(name="Jazz")
        enrollment = Enrollment.objects.create(
            student=self.student, discipline=discipline, enrolled_at=date(2026, 10, 1)
        )
        price = DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        self.charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=discipline,
            enrollment=enrollment,
            price_applied=price,
            period=date(2026, 10, 1),
            amount=price.amount,
        )

    def pay(self, amount):
        return register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal(amount),
            allocations=[(self.charge.pk, Decimal(amount))],
            received_by=self.staff,
        )

    def preview(self, amount=None, **kwargs):
        return preview_charge_adjustment(
            charge_id=self.charge.pk,
            resulting_amount=Decimal(amount) if amount is not None else None,
            reason="Motivo administrativo privado",
            actor=self.staff,
            **kwargs,
        )

    def confirm(self, preview):
        return confirm_charge_adjustment(
            charge_id=self.charge.pk, preview_token=preview["token"], actor=self.staff
        )

    def adjust(self, amount=None, **kwargs):
        return self.confirm(self.preview(amount, **kwargs))

    def totals(self):
        charge = charges_with_economic_totals().get(pk=self.charge.pk)
        credit = (
            students_with_available_credit(Student.objects.filter(pk=self.student.pk))
            .get()
            .available_credit
        )
        return charge.current_amount, charge.paid_amount, charge.outstanding, credit


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ChargeAdjustmentTests(AdjustmentFixtures, TestCase):
    def test_increase_preserves_snapshot_and_allows_payment_up_to_updated_total(self):
        self.adjust("35000")
        self.pay("35000")
        self.charge.refresh_from_db()
        self.assertEqual(self.charge.amount, Decimal("30000"))
        self.assertEqual(self.totals(), (35000, 35000, 0, 0))
        with self.assertRaises(ValidationError):
            self.pay("0.01")

    def test_reduction_without_payments(self):
        adjustment = self.adjust("15000")
        self.assertEqual(self.totals(), (15000, 0, 15000, 0))
        self.assertEqual(adjustment.previous_amount, 30000)
        self.assertEqual(adjustment.difference, -15000)
        self.assertEqual(adjustment.created_by, self.staff)
        self.assertTrue(adjustment.created_at)
        self.assertFalse(CreditRelease.objects.exists())

    def test_reduction_with_partial_payment_above_coverage_creates_no_credit(self):
        self.pay("10000")
        self.adjust("15000")
        self.assertEqual(self.totals(), (15000, 10000, 5000, 0))

    def test_reduction_below_payments_preserves_payment_and_allocation(self):
        payment = self.pay("20000")
        allocation = payment.allocations.get()
        adjustment = self.adjust("15000")
        self.assertEqual(self.totals(), (15000, 15000, 0, 5000))
        release = CreditRelease.objects.get()
        self.assertEqual(release.adjustment, adjustment)
        self.assertEqual(release.allocation, allocation)
        payment.refresh_from_db()
        allocation.refresh_from_db()
        self.assertEqual(payment.amount, 20000)
        self.assertEqual(allocation.amount, 20000)

    def test_annulment_without_payments(self):
        self.adjust("0")
        self.assertEqual(self.totals(), (0, 0, 0, 0))

    def test_annulment_with_payments_releases_exact_coverage(self):
        self.pay("30000")
        self.adjust("0")
        self.assertEqual(self.totals(), (0, 0, 0, 30000))

    def test_successive_adjustments_and_reversal_do_not_reconsume_credit(self):
        self.pay("20000")
        original = self.adjust("15000")
        self.adjust("10000")
        reversal = self.adjust(reverses_id=original.pk)
        self.assertEqual(reversal.difference, 15000)
        self.assertEqual(self.totals(), (25000, 10000, 15000, 10000))
        self.assertEqual(ChargeAdjustment.objects.count(), 3)
        with self.assertRaises(ValidationError):
            self.preview(reverses_id=original.pk)
        self.pay("15000")
        self.assertEqual(self.totals(), (25000, 25000, 0, 10000))

    def test_negative_reversal_is_rejected(self):
        increase = self.adjust("35000")
        self.adjust("1000")
        with self.assertRaises(ValidationError):
            self.preview(reverses_id=increase.pk)
        self.assertEqual(ChargeAdjustment.objects.count(), 2)

    def test_release_uses_latest_applications_first_without_double_release(self):
        first = self.pay("12000").allocations.get()
        second = self.pay("8000").allocations.get()
        self.adjust("15000")
        self.assertEqual(CreditRelease.objects.get().allocation, second)
        self.adjust("5000")
        self.assertEqual(
            sum(
                CreditRelease.objects.filter(allocation=second).values_list(
                    "amount", flat=True
                )
            ),
            8000,
        )
        self.assertEqual(
            sum(
                CreditRelease.objects.filter(allocation=first).values_list(
                    "amount", flat=True
                )
            ),
            7000,
        )
        self.assertEqual(self.totals(), (5000, 5000, 0, 15000))

    def test_repeated_confirmation_is_idempotent_even_after_later_adjustment(self):
        self.pay("20000")
        preview = self.preview("15000")
        first = self.confirm(preview)
        self.adjust("10000")
        repeated = self.confirm(preview)
        self.assertEqual(first.pk, repeated.pk)
        self.assertEqual(ChargeAdjustment.objects.count(), 2)
        self.assertEqual(self.totals(), (10000, 10000, 0, 10000))

    def test_stale_preview_after_payment_or_adjustment_requires_review(self):
        preview = self.preview("15000")
        self.pay("10000")
        with self.assertRaisesMessage(ValidationError, "cambió"):
            self.confirm(preview)
        preview = self.preview("15000")
        self.adjust("25000")
        with self.assertRaisesMessage(ValidationError, "cambió"):
            self.confirm(preview)

    def test_preview_does_not_write_and_rejects_invalid_inputs(self):
        self.preview("10000")
        self.assertFalse(ChargeAdjustment.objects.exists())
        for amount in ("-1", "30000", "0.001", "NaN", "Infinity"):
            with self.subTest(amount=amount), self.assertRaises(ValidationError):
                self.preview(amount)
        with self.assertRaises(ValidationError):
            preview_charge_adjustment(
                charge_id=self.charge.pk,
                resulting_amount=Decimal("100"),
                reason="  ",
                actor=self.staff,
            )

    def test_permission_and_signed_actor_payload_are_enforced(self):
        preview = self.preview("10000")
        with self.assertRaises(PermissionDenied):
            confirm_charge_adjustment(
                charge_id=self.charge.pk,
                preview_token=preview["token"],
                actor=self.owner,
            )
        other_staff = get_user_model().objects.create_superuser(
            "other@example.com", "password"
        )
        with self.assertRaises(PermissionDenied):
            confirm_charge_adjustment(
                charge_id=self.charge.pk,
                preview_token=preview["token"],
                actor=other_staff,
            )
        with self.assertRaises(ValidationError):
            self.confirm({"token": preview["token"] + "tampered"})
        self.assertFalse(ChargeAdjustment.objects.exists())

    def test_failure_during_release_rolls_back_adjustment_and_all_releases(self):
        self.pay("10000")
        self.pay("10000")
        preview = self.preview("0")
        original_save = CreditRelease.save
        calls = []

        def fail_second(release, *args, **kwargs):
            calls.append(release)
            if len(calls) == 2:
                raise ValidationError("fallo")
            return original_save(release, *args, **kwargs)

        with (
            patch.object(CreditRelease, "save", fail_second),
            self.assertRaises(ValidationError),
        ):
            self.confirm(preview)
        self.assertFalse(ChargeAdjustment.objects.exists())
        self.assertFalse(CreditRelease.objects.exists())
        self.confirm(preview)
        self.assertEqual(self.totals(), (0, 0, 0, 20000))

    def test_adjustments_and_releases_are_immutable(self):
        self.pay("20000")
        adjustment = self.adjust("15000")
        for movement in (adjustment, CreditRelease.objects.get()):
            with self.assertRaises(ValidationError):
                movement.save()
            with self.assertRaises(ValidationError):
                movement.delete()

    def test_database_rejects_inconsistent_adjustment_and_nonpositive_release(self):
        self.pay("20000")
        adjustment = self.adjust("15000")
        with self.assertRaises(IntegrityError), transaction.atomic():
            ChargeAdjustment.objects.bulk_create(
                [
                    ChargeAdjustment(
                        charge=self.charge,
                        previous_amount=15000,
                        resulting_amount=10000,
                        difference=1000,
                        reason="test",
                        created_by=self.staff,
                        operation_id=uuid4(),
                    )
                ]
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            CreditRelease.objects.filter(adjustment=adjustment).update(amount=0)

    def test_transfer_confirmation_uses_adjusted_total(self):
        self.adjust("35000")
        intent = register_transfer_intent(
            student_id=self.student.pk, amount=Decimal("35000"), created_by=self.staff
        )
        confirm_transfer(
            intent_id=intent.pk,
            allocations=[(self.charge.pk, Decimal("35000"))],
            confirmed_by=self.staff,
        )
        self.assertEqual(self.totals(), (35000, 35000, 0, 0))

    def test_admin_preview_confirmation_replay_and_view_only_denial(self):
        self.client.force_login(self.staff)
        url = reverse("admin:billing_monthlycharge_adjust", args=(self.charge.pk,))
        response = self.client.post(
            url, {"resulting_amount": "15000", "reason": "Error", "_preview": "1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ChargeAdjustment.objects.exists())
        token = response.context["preview_token"]
        for _ in range(2):
            response = self.client.post(url, {"preview_token": token, "_confirm": "1"})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(ChargeAdjustment.objects.count(), 1)
        viewer = get_user_model().objects.create_user(
            "viewer@example.com", "password", is_staff=True
        )
        viewer.user_permissions.add(
            Permission.objects.get(codename="view_monthlycharge")
        )
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(
            self.client.post(
                url, {"preview_token": token, "_confirm": "1"}
            ).status_code,
            403,
        )

    def test_admin_stale_confirmation_shows_error_without_writing(self):
        self.client.force_login(self.staff)
        url = reverse("admin:billing_monthlycharge_adjust", args=(self.charge.pk,))
        preview = self.client.post(
            url, {"resulting_amount": "15000", "reason": "Error", "_preview": "1"}
        )
        self.pay("10000")
        response = self.client.post(
            url, {"preview_token": preview.context["preview_token"], "_confirm": "1"}
        )
        self.assertContains(response, "cambió desde la vista previa")
        self.assertFalse(ChargeAdjustment.objects.exists())

    def test_private_query_returns_consistent_totals_credit_without_internal_audit(
        self,
    ):
        self.pay("20000")
        self.adjust("15000")
        self.client.force_login(self.owner)
        response = self.client.get(reverse("billing-my-charges"))
        self.assertEqual(response["Cache-Control"], "no-store")
        data = response.json()
        self.assertEqual(
            data["summary"],
            {"amount": "15000.00", "paidAmount": "15000.00", "balance": "0.00"},
        )
        self.assertEqual(data["credits"][0]["availableAmount"], "5000.00")
        self.assertEqual(data["results"][0]["originalAmount"], "30000.00")
        self.assertEqual(data["results"][0]["releasedAmount"], "5000.00")
        self.assertNotContains(response, "Motivo administrativo privado")
        self.assertNotContains(response, self.staff.email)
        self.assertNotIn("reason", data["results"][0]["adjustments"][0])

    def test_private_credits_follow_guardianship_and_do_not_leak_to_other_users(self):
        self.pay("20000")
        self.adjust("0")
        self.student.date_of_birth = date(2015, 1, 1)
        self.student.save()
        guardian = get_user_model().objects.create_user(
            "guardian@example.com", "password"
        )
        relationship = GuardianRelationship.objects.create(
            guardian=guardian, student=self.student, created_by=self.staff
        )
        self.client.force_login(guardian)
        self.assertEqual(
            self.client.get(reverse("billing-my-charges")).json()["credits"][0][
                "availableAmount"
            ],
            "20000.00",
        )
        from django.utils import timezone

        relationship.revoked_at = timezone.now()
        relationship.revoked_by = self.staff
        relationship.save()
        data = self.client.get(reverse("billing-my-charges")).json()
        self.assertEqual(data["credits"], [])
        self.assertEqual(data["results"], [])

    def test_annulled_charge_is_not_classified_as_scholarship(self):
        self.adjust("0")
        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(reverse("billing-my-charges")).json()["results"][0][
                "status"
            ],
            "adjusted_to_zero",
        )


class ConcurrentAdjustmentTests(AdjustmentFixtures, TransactionTestCase):
    def run_together(self, operations):
        barrier = threading.Barrier(2)

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    operation()
                    return "success"
                except ValidationError:
                    return "review"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(run, operations))

    def test_simultaneous_adjustments_do_not_release_twice(self):
        self.pay("20000")
        previews = [self.preview("15000"), self.preview("10000")]
        outcomes = self.run_together(
            [lambda: self.confirm(previews[0]), lambda: self.confirm(previews[1])]
        )
        self.assertCountEqual(outcomes, ["success", "review"])
        self.assertEqual(ChargeAdjustment.objects.count(), 1)
        total, paid, balance, credit = self.totals()
        self.assertEqual(total, paid)
        self.assertEqual(balance, 0)
        self.assertEqual(paid + credit, 20000)

    def test_simultaneous_replay_records_one_operation(self):
        self.pay("20000")
        preview = self.preview("15000")
        outcomes = self.run_together(
            [lambda: self.confirm(preview), lambda: self.confirm(preview)]
        )
        self.assertEqual(outcomes, ["success", "success"])
        self.assertEqual(ChargeAdjustment.objects.count(), 1)
        self.assertEqual(CreditRelease.objects.count(), 1)

    def test_payment_and_adjustment_share_lock_and_preserve_money(self):
        preview = self.preview("10000")
        outcomes = self.run_together(
            [lambda: self.confirm(preview), lambda: self.pay("20000")]
        )
        self.assertCountEqual(outcomes, ["success", "review"])
        total, paid, balance, credit = self.totals()
        self.assertEqual(total - paid, balance)
        self.assertGreaterEqual(balance, 0)
        self.assertEqual(credit, 0)

    def test_transfer_confirmation_and_adjustment_share_lock(self):
        intent = register_transfer_intent(
            student_id=self.student.pk, amount=Decimal("20000"), created_by=self.staff
        )
        preview = self.preview("10000")
        outcomes = self.run_together(
            [
                lambda: self.confirm(preview),
                lambda: confirm_transfer(
                    intent_id=intent.pk,
                    allocations=[(self.charge.pk, Decimal("20000"))],
                    confirmed_by=self.staff,
                ),
            ]
        )
        self.assertCountEqual(outcomes, ["success", "review"])
        self.assertGreaterEqual(self.totals()[2], 0)
        self.assertLessEqual(PaymentAllocation.objects.count(), 1)
