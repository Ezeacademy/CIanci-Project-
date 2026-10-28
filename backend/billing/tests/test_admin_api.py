from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from academy.models import Discipline, Enrollment, Student
from billing.adjustments import confirm_charge_adjustment, preview_charge_adjustment
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import CreditRelease
from payments.services import register_cash_payment

User = get_user_model()
PASSWORD = "Admin-monthly-charge-read-passphrase-93!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AdminMonthlyChargeAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            "billing-manager@example.com", PASSWORD, is_staff=True
        )
        self.student = Student.objects.create(first_name="Ana", last_name="Cianci")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrolled_at=date(2020, 1, 1),
        )
        self.price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2020, 1, 1),
        )
        self.charge = self.create_charge(date(2026, 10, 1))
        self.list_url = reverse("admin-billing-monthly-charges")
        self.detail_url = reverse(
            "admin-billing-monthly-charge-detail", args=(self.charge.pk,)
        )
        self.grant_read_permissions()
        self.client.force_login(self.staff)

    def create_charge(self, period, discount_amount=Decimal("0.00")):
        return MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            price_applied=self.price,
            period=period,
            base_amount=self.price.amount,
            discount_amount=discount_amount,
            scholarship_percentage=20 if discount_amount else None,
            amount=self.price.amount - discount_amount,
        )

    def grant_read_permissions(self):
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label__in=("billing", "payments"),
                codename__in=(
                    "view_monthlycharge",
                    "view_chargeadjustment",
                    "view_payment",
                    "adjust_monthlycharge",
                ),
            )
        )

    def test_anonymous_and_staff_without_all_financial_permissions_are_denied(self):
        self.client.logout()
        self.assertIn(self.client.get(self.list_url).status_code, (401, 403))

        self.client.force_login(
            User.objects.create_user(
                "no-permissions@example.com", PASSWORD, is_staff=True
            )
        )
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.get(self.detail_url).status_code, 403)

    def test_filtered_summary_uses_current_amount_partial_payments_and_adjustments(
        self,
    ):
        register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("10000.00"),
            allocations=[(self.charge.pk, Decimal("10000.00"))],
            received_by=self.staff,
        )
        preview = preview_charge_adjustment(
            charge_id=self.charge.pk,
            resulting_amount=Decimal("20000.00"),
            reason="Corrección auditada",
            actor=self.staff,
        )
        confirm_charge_adjustment(
            preview_token=preview["token"], actor=self.staff, charge_id=self.charge.pk
        )

        response = self.client.get(
            self.list_url,
            {
                "q": "Ana Cianci",
                "period": "2026-10",
                "discipline": self.discipline.pk,
                "status": "pending",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json()["summary"],
            {
                "currentAmount": "20000.00",
                "paidAmount": "10000.00",
                "outstanding": "10000.00",
            },
        )
        row = response.json()["results"][0]
        self.assertEqual(row["baseAmount"], "30000.00")
        self.assertEqual(row["originalAmount"], "30000.00")
        self.assertEqual(row["adjustmentAmount"], "-10000.00")
        self.assertEqual(row["paidAmount"], "10000.00")
        self.assertEqual(row["outstanding"], "10000.00")

    def test_filters_validate_period_and_status(self):
        invalid_period = self.client.get(self.list_url, {"period": "2026-13"})
        invalid_status = self.client.get(self.list_url, {"status": "overdue"})

        self.assertEqual(invalid_period.status_code, 400)
        self.assertEqual(invalid_status.status_code, 400)

    def test_pagination_keeps_summary_for_the_entire_filtered_result(self):
        for month_index in range(26):
            year, zero_based_month = divmod(month_index, 12)
            period = date(2021 + year, zero_based_month + 1, 1)
            self.create_charge(period)

        first_page = self.client.get(self.list_url, {"q": "Ana", "page": 1})
        second_page = self.client.get(self.list_url, {"q": "Ana", "page": 2})

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.json()["count"], 27)
        self.assertEqual(len(first_page.json()["results"]), 25)
        self.assertIsNotNone(first_page.json()["next"])
        self.assertEqual(len(second_page.json()["results"]), 2)
        self.assertEqual(first_page.json()["summary"], second_page.json()["summary"])

    def test_summary_uses_one_sql_aggregate_for_small_and_large_filtered_sets(self):
        for month_index in range(30):
            year, zero_based_month = divmod(month_index, 12)
            period = date(2021 + year, zero_based_month + 1, 1)
            self.create_charge(period)

        aggregate_query_counts = []
        for query_params in (
            {"period": "2026-10"},
            {"q": "Ana", "page": 2},
        ):
            with CaptureQueriesContext(connection) as captured_queries:
                response = self.client.get(self.list_url, query_params)

            aggregate_queries = [
                query["sql"]
                for query in captured_queries
                if query["sql"].lstrip().lower().startswith("select sum(")
                and '"billing_monthlycharge"' in query["sql"].lower()
            ]
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(aggregate_queries), 1)
            self.assertIn("sum(", aggregate_queries[0].lower())
            aggregate_query_counts.append(len(aggregate_queries))

        self.assertEqual(aggregate_query_counts, [1, 1])

    def test_summary_uses_retained_payments_after_credit_release(self):
        register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("20000.00"),
            allocations=[(self.charge.pk, Decimal("20000.00"))],
            received_by=self.staff,
        )
        preview = preview_charge_adjustment(
            charge_id=self.charge.pk,
            resulting_amount=Decimal("15000.00"),
            reason="Ajuste con excedente",
            actor=self.staff,
        )
        confirm_charge_adjustment(
            preview_token=preview["token"], actor=self.staff, charge_id=self.charge.pk
        )
        self.create_charge(date(2026, 11, 1), discount_amount=Decimal("6000.00"))

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["summary"],
            {
                "currentAmount": "39000.00",
                "paidAmount": "15000.00",
                "outstanding": "24000.00",
            },
        )

    def test_detail_shows_payment_allocation_adjustment_and_released_credit_history(
        self,
    ):
        register_cash_payment(
            student_id=self.student.pk,
            amount=Decimal("20000.00"),
            allocations=[(self.charge.pk, Decimal("20000.00"))],
            received_by=self.staff,
        )
        preview = preview_charge_adjustment(
            charge_id=self.charge.pk,
            resulting_amount=Decimal("15000.00"),
            reason="Ajuste con excedente",
            actor=self.staff,
        )
        confirm_charge_adjustment(
            preview_token=preview["token"], actor=self.staff, charge_id=self.charge.pk
        )

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["paidAmount"], "15000.00")
        self.assertEqual(payload["outstanding"], "0.00")
        self.assertEqual(len(payload["payments"]), 1)
        self.assertEqual(payload["payments"][0]["allocatedAmount"], "20000.00")
        self.assertEqual(payload["payments"][0]["releasedAmount"], "5000.00")
        self.assertEqual(payload["payments"][0]["appliedAmount"], "15000.00")
        self.assertEqual(payload["adjustments"][0]["reason"], "Ajuste con excedente")
        self.assertEqual(CreditRelease.objects.count(), 1)
        self.assertEqual(MonthlyCharge.objects.count(), 1)
