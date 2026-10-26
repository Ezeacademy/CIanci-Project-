from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import Payment, PaymentIntent
from payments.services import (
    register_cash_payment,
    register_transfer_intent,
    reject_transfer,
)

User = get_user_model()
PASSWORD = "Safe-financial-account-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class PrivateFinancialAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user("owner@example.com", PASSWORD)
        self.guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        self.audit_user = User.objects.create_user("staff@example.com", PASSWORD)
        self.student = Student.objects.create(
            first_name="Cande", last_name="Manzo", user=self.owner
        )
        self.minor = Student.objects.create(
            first_name="Sofía", last_name="Manzo", date_of_birth=date(2015, 4, 1)
        )
        self.other = Student.objects.create(first_name="Ana", last_name="Ajena")
        GuardianRelationship.objects.create(
            guardian=self.guardian, student=self.minor, created_by=self.audit_user
        )
        self.jazz = Discipline.objects.create(name="Jazz")
        self.classic = Discipline.objects.create(name="Clásico")
        self.jazz_charge = self.create_charge(self.student, self.jazz, "30000.00")
        self.classic_charge = self.create_charge(self.student, self.classic, "25000.00")
        self.minor_charge = self.create_charge(self.minor, self.jazz, "30000.00")
        self.other_charge = self.create_charge(self.other, self.classic, "25000.00")

    def create_charge(self, student, discipline, amount):
        enrollment = Enrollment.objects.create(
            student=student, discipline=discipline, enrolled_at=date(2026, 10, 1)
        )
        price, _ = DisciplinePrice.objects.get_or_create(
            discipline=discipline,
            effective_month=date(2026, 10, 1),
            defaults={"amount": Decimal(amount), "created_by": self.audit_user},
        )
        return MonthlyCharge.objects.create(
            student=student,
            discipline=discipline,
            enrollment=enrollment,
            period=date(2026, 10, 1),
            price_applied=price,
            amount=Decimal(amount),
        )

    def test_owner_sees_original_charges_allocations_and_only_confirmed_money(self):
        register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("20000.00"),
            allocations=[
                (self.jazz_charge.pk, Decimal("15000.00")),
                (self.classic_charge.pk, Decimal("5000.00")),
            ],
            received_by=self.audit_user,
            reference="private-payment-reference",
        )
        register_transfer_intent(
            student_id=self.student.pk,
            amount=Decimal("1000.00"),
            created_by=self.owner,
            reference="private-proof-reference",
        )
        rejected = register_transfer_intent(
            student_id=self.student.pk,
            amount=Decimal("1000.00"),
            created_by=self.owner,
        )
        reject_transfer(intent_id=rejected.pk, rejected_by=self.audit_user)
        self.client.force_login(self.owner)

        charges = self.client.get(reverse("billing-my-charges"))
        payments = self.client.get(reverse("payments-my-confirmed"))
        intents = self.client.get(reverse("payments-my-intents"))

        self.assertEqual(charges.status_code, 200)
        self.assertEqual(charges["Cache-Control"], "no-store")
        self.assertEqual(
            charges.json()["summary"],
            {"amount": "55000.00", "paidAmount": "20000.00", "balance": "35000.00"},
        )
        amounts = {
            item["discipline"]: (item["amount"], item["paidAmount"], item["balance"])
            for item in charges.json()["results"]
        }
        self.assertEqual(amounts["Jazz"], ("30000.00", "15000.00", "15000.00"))
        self.assertEqual(amounts["Clásico"], ("25000.00", "5000.00", "20000.00"))
        self.assertEqual(payments.status_code, 200)
        self.assertEqual(payments["Cache-Control"], "no-store")
        payment = payments.json()["results"][0]
        self.assertEqual(payment["amount"], "20000.00")
        self.assertEqual(len(payment["allocations"]), 2)
        self.assertNotIn("reference", payment)
        self.assertEqual(intents.status_code, 200)
        self.assertEqual(intents["Cache-Control"], "no-store")
        self.assertEqual(
            {item["status"] for item in intents.json()["results"]},
            {PaymentIntent.Status.PENDING, PaymentIntent.Status.REJECTED},
        )
        self.assertTrue(
            all("reference" not in item for item in intents.json()["results"])
        )
        self.assertEqual(Payment.objects.count(), 1)

    def test_guardian_access_ends_after_relationship_revocation(self):
        register_cash_payment(
            student_id=self.minor.pk,
            amount=Decimal("5000.00"),
            allocations=[(self.minor_charge.pk, Decimal("5000.00"))],
            received_by=self.audit_user,
        )
        register_transfer_intent(
            student_id=self.minor.pk,
            amount=Decimal("1000.00"),
            created_by=self.guardian,
        )
        self.client.force_login(self.guardian)
        response = self.client.get(reverse("billing-my-charges"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["student"]["firstName"], "Sofía"
        )
        self.assertEqual(
            self.client.get(reverse("payments-my-confirmed")).json()["count"], 1
        )
        self.assertEqual(
            self.client.get(reverse("payments-my-intents")).json()["count"], 1
        )

        relationship = GuardianRelationship.objects.get(guardian=self.guardian)
        relationship.revoked_at = timezone.now()
        relationship.revoked_by = self.audit_user
        relationship.save(update_fields=("revoked_at", "revoked_by"))
        response = self.client.get(reverse("billing-my-charges"))
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(response.json()["summary"]["balance"], "0.00")

    def test_unassociated_user_sees_no_records_and_anonymous_is_denied(self):
        anonymous = self.client.get(reverse("billing-my-charges"))
        self.assertIn(anonymous.status_code, (401, 403))
        self.assertIn(
            self.client.get(reverse("payments-my-confirmed")).status_code, (401, 403)
        )
        unrelated = User.objects.create_user("unrelated@example.com", PASSWORD)
        unrelated.is_staff = True
        unrelated.save(update_fields=("is_staff",))
        self.client.force_login(unrelated)
        response = self.client.get(reverse("billing-my-charges"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(response.json()["summary"]["amount"], "0.00")
        self.assertEqual(
            self.client.get(reverse("payments-my-confirmed")).json()["count"], 0
        )
        self.assertEqual(
            self.client.get(reverse("payments-my-intents")).json()["count"], 0
        )

    def test_owner_financial_responses_exclude_other_students(self):
        self.client.force_login(self.owner)
        charges = self.client.get(reverse("billing-my-charges")).json()
        self.assertEqual(charges["count"], 2)
        self.assertTrue(
            all(item["student"]["accessType"] == "self" for item in charges["results"])
        )

    def test_paid_charge_and_payment_allocations_preserve_multiple_periods(self):
        prior_month = date(2026, 9, 1)
        previous_enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrolled_at=date(2026, 9, 1),
            ended_at=date(2026, 9, 30),
        )
        previous_price = DisciplinePrice.objects.create(
            discipline=self.jazz,
            amount=Decimal("28000.00"),
            effective_month=prior_month,
            created_by=self.audit_user,
        )
        previous_charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.jazz,
            enrollment=previous_enrollment,
            period=prior_month,
            price_applied=previous_price,
            amount=previous_price.amount,
        )
        register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("58000.00"),
            allocations=[
                (previous_charge.pk, Decimal("28000.00")),
                (self.jazz_charge.pk, Decimal("30000.00")),
            ],
            received_by=self.audit_user,
        )
        self.client.force_login(self.owner)

        charges = self.client.get(reverse("billing-my-charges")).json()
        payments = self.client.get(reverse("payments-my-confirmed")).json()

        self.assertEqual(charges["summary"]["balance"], "25000.00")
        paid_jazz = next(
            item for item in charges["results"] if item["period"] == "2026-10"
        )
        self.assertEqual(paid_jazz["balance"], "0.00")
        self.assertEqual(
            {item["period"] for item in payments["results"][0]["allocations"]},
            {"2026-09", "2026-10"},
        )
