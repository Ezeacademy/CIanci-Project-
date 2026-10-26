from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class BillingAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            "admin@example.com", "Safe-admin-password-92!"
        )
        self.client = Client()
        self.client.force_login(self.admin_user)
        self.student = Student.objects.create(first_name="Cande", last_name="Manzo")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.enrollment = Enrollment.objects.create(
            student=self.student, discipline=self.discipline
        )

    def test_price_admin_records_author_and_allows_new_effective_month(self):
        response = self.client.post(
            reverse("admin:billing_disciplineprice_add"),
            {
                "discipline": self.discipline.pk,
                "amount": "30000.00",
                "currency": "ARS",
                "effective_month": "2026-10-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        price = DisciplinePrice.objects.get()
        self.assertEqual(price.created_by, self.admin_user)

    def test_tariff_admin_accepts_whole_peso_input_without_decimal_suffix(self):
        response = self.client.post(
            reverse("admin:billing_disciplineprice_add"),
            {
                "discipline": self.discipline.pk,
                "amount": "30000",
                "currency": "ARS",
                "effective_month": "2026-10-01",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(DisciplinePrice.objects.get().amount, Decimal("30000.00"))

    def test_monthly_charge_admin_is_read_only(self):
        price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 10, 1),
            price_applied=price,
            amount=price.amount,
        )
        change_url = reverse("admin:billing_monthlycharge_change", args=(charge.pk,))

        response = self.client.get(change_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "$ 30.000")
        self.assertNotContains(response, "30000.00")
        self.assertEqual(
            self.client.get(reverse("admin:billing_monthlycharge_add")).status_code,
            403,
        )

    def test_tariff_list_uses_argentine_money_format(self):
        DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.50"),
            effective_month=date(2026, 11, 1),
        )

        response = self.client.get(reverse("admin:billing_disciplineprice_changelist"))

        self.assertContains(response, "$ 30.000,50")
        self.assertNotContains(response, "30000.50")

    def test_enrollment_admin_allows_unreferenced_delete_and_blocks_referenced_delete(
        self,
    ):
        disposable = Enrollment.objects.create(
            student=Student.objects.create(first_name="Ana", last_name="Cianci"),
            discipline=self.discipline,
            enrolled_at=date(2026, 9, 1),
            ended_at=date(2026, 10, 1),
        )
        delete_url = reverse("admin:academy_enrollment_delete", args=(disposable.pk,))
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        response = self.client.post(delete_url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(pk=disposable.pk).exists())

        price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 10, 1),
            price_applied=price,
            amount=price.amount,
        )
        protected_delete_url = reverse(
            "admin:academy_enrollment_delete", args=(self.enrollment.pk,)
        )
        self.assertEqual(self.client.get(protected_delete_url).status_code, 403)
        self.assertTrue(Enrollment.objects.filter(pk=charge.enrollment_id).exists())

    def test_enrollment_admin_rejects_baja_before_an_issued_charge_period(self):
        historic_enrollment = Enrollment.objects.create(
            student=Student.objects.create(first_name="Eva", last_name="Cianci"),
            discipline=self.discipline,
            enrolled_at=date(2026, 9, 1),
        )
        price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            amount=Decimal("30000.00"),
            effective_month=date(2026, 10, 1),
        )
        MonthlyCharge.objects.create(
            student=historic_enrollment.student,
            discipline=self.discipline,
            enrollment=historic_enrollment,
            period=date(2026, 10, 1),
            price_applied=price,
            amount=price.amount,
        )

        response = self.client.post(
            reverse("admin:academy_enrollment_change", args=(historic_enrollment.pk,)),
            {
                "student": historic_enrollment.student_id,
                "discipline": self.discipline.pk,
                "enrolled_at": "2026-09-01",
                "ended_at": "2026-09-30",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "no puede ser anterior al inicio")
        historic_enrollment.refresh_from_db()
        self.assertIsNone(historic_enrollment.ended_at)
