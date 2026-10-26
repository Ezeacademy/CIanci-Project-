from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse

from academy.models import Discipline, Enrollment, Student
from billing.models import DisciplinePrice, MonthlyCharge, Scholarship

User = get_user_model()


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class BillingAdminExperienceTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            "billing-admin@example.com", "Safe-billing-admin-password-92!"
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

    def create_enrollment(self, *, student_name, discipline, enrolled_at):
        student = Student.objects.create(first_name=student_name, last_name="Manzo")
        return Enrollment.objects.create(
            student=student,
            discipline=discipline,
            enrolled_at=enrolled_at,
        )

    def add_discipline_price(self, discipline, amount, effective_month):
        return DisciplinePrice.objects.create(
            discipline=discipline,
            amount=Decimal(amount),
            effective_month=effective_month,
            created_by=self.admin_user,
        )

    def test_discipline_can_be_created_with_or_without_initial_price(self):
        response = self.client.post(
            reverse("admin:academy_discipline_add"),
            {
                "name": "Jazz",
                "is_active": "on",
                "initial_monthly_price": "30000.00",
                "initial_price_effective_month": "2026-10-01",
            },
        )

        self.assertEqual(response.status_code, 302)
        jazz = Discipline.objects.get(name="Jazz")
        jazz_price = DisciplinePrice.objects.get(discipline=jazz)
        self.assertEqual(jazz_price.amount, Decimal("30000.00"))
        self.assertEqual(jazz_price.effective_month, date(2026, 10, 1))
        self.assertEqual(jazz_price.created_by, self.admin_user)

        response = self.client.post(
            reverse("admin:academy_discipline_add"),
            {"name": "Contemporáneo", "is_active": "on"},
        )

        self.assertEqual(response.status_code, 302)
        contemporary = Discipline.objects.get(name="Contemporáneo")
        self.assertFalse(DisciplinePrice.objects.filter(discipline=contemporary).exists())

    def test_student_admin_can_create_audited_scholarship_inline(self):
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        jazz = Discipline.objects.create(name="Jazz")
        change_url = reverse("admin:academy_student_change", args=(student.pk,))

        page = self.client.get(change_url)
        self.assertContains(page, "Becas")
        self.assertContains(page, "Las mensualidades ya emitidas no se modificarán")

        response = self.client.post(
            change_url,
            {
                "first_name": student.first_name,
                "last_name": student.last_name,
                "date_of_birth": "",
                "user": "",
                "scholarships-TOTAL_FORMS": "1",
                "scholarships-INITIAL_FORMS": "0",
                "scholarships-MIN_NUM_FORMS": "0",
                "scholarships-MAX_NUM_FORMS": "1000",
                "scholarships-0-discipline": jazz.pk,
                "scholarships-0-percentage": "50",
                "scholarships-0-start_month": "2026-10-01",
                "scholarships-0-end_month": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        scholarship = Scholarship.objects.get()
        self.assertEqual(scholarship.student, student)
        self.assertEqual(scholarship.discipline, jazz)
        self.assertEqual(scholarship.percentage, 50)
        self.assertEqual(scholarship.created_by, self.admin_user)

    def test_student_admin_only_shows_scholarship_editor_with_billing_permission(self):
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        enrollment_operator = User.objects.create_user(
            "enrollment-operator@example.com",
            "Safe-enrollment-operator-92!",
            is_staff=True,
        )
        change_student_permission = Permission.objects.get(
            content_type__app_label="academy",
            codename="change_student",
        )
        enrollment_operator.user_permissions.add(change_student_permission)
        self.client.force_login(enrollment_operator)

        response = self.client.get(
            reverse("admin:academy_student_change", args=(student.pk,))
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "scholarships-0-percentage")
        self.assertNotIn(
            "billing.add_scholarship", enrollment_operator.get_all_permissions()
        )

    def test_initial_price_validation_and_save_are_atomic(self):
        invalid_response = self.client.post(
            reverse("admin:academy_discipline_add"),
            {
                "name": "Jazz",
                "is_active": "on",
                "initial_monthly_price": "30000.00",
                "initial_price_effective_month": "2026-10-15",
            },
        )
        self.assertEqual(invalid_response.status_code, 200)
        self.assertFalse(Discipline.objects.filter(name="Jazz").exists())

        discipline_admin = admin.site._registry[Discipline]
        admin_request = RequestFactory().post("/admin/academy/discipline/add/")
        admin_request.user = self.admin_user
        new_discipline = Discipline(name="Salsa")
        discipline_form = SimpleNamespace(
            cleaned_data={
                "initial_monthly_price": Decimal("25000.00"),
                "initial_price_effective_month": date(2026, 10, 1),
            }
        )
        with patch(
            "academy.admin.DisciplinePrice.objects.create",
            side_effect=IntegrityError("simulated price insert failure"),
        ):
            with self.assertRaises(IntegrityError):
                discipline_admin.save_model(
                    admin_request, new_discipline, discipline_form, False
                )
        self.assertFalse(Discipline.objects.filter(name="Salsa").exists())

    @patch("academy.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_current_month_enrollment_generates_one_full_monthly_charge(self, _today):
        jazz = Discipline.objects.create(name="Jazz")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        student = Student.objects.create(first_name="Cande", last_name="Manzo")

        response = self.client.post(
            reverse("admin:academy_enrollment_add"),
            {
                "student": student.pk,
                "discipline": jazz.pk,
                "enrolled_at": "2026-10-15",
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        monthly_charge = MonthlyCharge.objects.get(student=student, discipline=jazz)
        self.assertEqual(monthly_charge.period, date(2026, 10, 1))
        self.assertEqual(monthly_charge.amount, Decimal("30000.00"))

    @patch("academy.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_future_enrollment_and_edit_do_not_generate_a_monthly_charge(self, _today):
        jazz = Discipline.objects.create(name="Jazz")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        future_student = Student.objects.create(first_name="Sofía", last_name="Manzo")

        self.client.post(
            reverse("admin:academy_enrollment_add"),
            {
                "student": future_student.pk,
                "discipline": jazz.pk,
                "enrolled_at": "2026-11-01",
                "ended_at": "",
            },
        )
        self.assertFalse(MonthlyCharge.objects.exists())

        historic_student = Student.objects.create(first_name="Ana", last_name="Manzo")
        historic_enrollment = Enrollment.objects.create(
            student=historic_student,
            discipline=jazz,
            enrolled_at=date(2026, 9, 1),
        )
        self.client.post(
            reverse("admin:academy_enrollment_change", args=(historic_enrollment.pk,)),
            {
                "student": historic_student.pk,
                "discipline": jazz.pk,
                "enrolled_at": "2026-09-02",
                "ended_at": "",
            },
        )
        self.assertFalse(MonthlyCharge.objects.exists())

    @patch("academy.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_missing_price_keeps_enrollment_and_reports_omitted_charge(self, _today):
        jazz = Discipline.objects.create(name="Jazz")
        student = Student.objects.create(first_name="Luz", last_name="Manzo")

        response = self.client.post(
            reverse("admin:academy_enrollment_add"),
            {
                "student": student.pk,
                "discipline": jazz.pk,
                "enrolled_at": "2026-10-15",
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Enrollment.objects.filter(student=student).exists())
        self.assertFalse(MonthlyCharge.objects.exists())
        follow_response = self.client.get(response.url)
        self.assertContains(follow_response, "no se generó su mensualidad")

    @patch("academy.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_enrollment_permission_does_not_grant_charge_generation_permission(
        self, _today
    ):
        jazz = Discipline.objects.create(name="Jazz")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        enrollment_operator = User.objects.create_user(
            "enrollment-operator@example.com", "Safe-enrollment-operator-92!"
        )
        enrollment_operator.is_staff = True
        enrollment_operator.save(update_fields=("is_staff",))
        enrollment_content_type = ContentType.objects.get_for_model(Enrollment)
        add_enrollment_permission = Permission.objects.get(
            content_type=enrollment_content_type,
            codename="add_enrollment",
        )
        enrollment_operator.user_permissions.add(add_enrollment_permission)
        self.client.force_login(enrollment_operator)

        response = self.client.post(
            reverse("admin:academy_enrollment_add"),
            {
                "student": student.pk,
                "discipline": jazz.pk,
                "enrolled_at": "2026-10-15",
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Enrollment.objects.filter(student=student).exists())
        self.assertFalse(MonthlyCharge.objects.exists())
        self.assertContains(
            self.client.get(response.url), "no tiene permiso para emitir cargos"
        )
        self.assertNotIn(
            "billing.add_monthlycharge", enrollment_operator.get_all_permissions()
        )

    @patch("billing.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_monthly_management_generates_future_period_idempotently(self, _today):
        jazz = Discipline.objects.create(name="Jazz")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        self.create_enrollment(
            student_name="Cande",
            discipline=jazz,
            enrolled_at=date(2026, 10, 1),
        )
        management_url = reverse("admin:billing_monthlycharge_management")

        preview_response = self.client.get(
            management_url, {"month": "11", "year": "2026"}
        )
        self.assertEqual(preview_response.status_code, 200)
        self.assertContains(preview_response, "1 mensualidad esperada")
        self.assertContains(preview_response, "1 mensualidad pendiente")

        post_data = {"month": "11", "year": "2026"}
        generated_response = self.client.post(management_url, post_data)
        self.assertEqual(generated_response.status_code, 302)
        self.assertTrue(
            MonthlyCharge.objects.filter(period=date(2026, 11, 1)).exists()
        )
        repeated_response = self.client.post(management_url, post_data)
        self.assertEqual(repeated_response.status_code, 302)
        self.assertEqual(
            MonthlyCharge.objects.filter(period=date(2026, 11, 1)).count(), 1
        )

    @patch("billing.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_monthly_management_skips_missing_price_and_creates_valid_charges(
        self, _today
    ):
        jazz = Discipline.objects.create(name="Jazz")
        classic = Discipline.objects.create(name="Clásico")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        self.create_enrollment(
            student_name="Cande", discipline=jazz, enrolled_at=date(2026, 10, 1)
        )
        self.create_enrollment(
            student_name="Sofía", discipline=classic, enrolled_at=date(2026, 10, 1)
        )
        management_url = reverse("admin:billing_monthlycharge_management")

        preview_response = self.client.get(
            management_url, {"month": "10", "year": "2026"}
        )
        self.assertContains(preview_response, "Clásico")
        self.assertContains(preview_response, "2 mensualidades esperadas")

        self.client.post(management_url, {"month": "10", "year": "2026"})

        self.assertEqual(MonthlyCharge.objects.count(), 1)
        self.assertEqual(MonthlyCharge.objects.get().discipline, jazz)

    @patch("billing.admin.timezone.localdate", return_value=date(2026, 10, 26))
    def test_monthly_management_requires_permission_and_csrf_for_generation(
        self, _today
    ):
        jazz = Discipline.objects.create(name="Jazz")
        self.add_discipline_price(jazz, "30000.00", date(2026, 10, 1))
        self.create_enrollment(
            student_name="Cande", discipline=jazz, enrolled_at=date(2026, 10, 1)
        )
        management_url = reverse("admin:billing_monthlycharge_management")
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin_user)

        preview_response = csrf_client.get(
            management_url, {"month": "10", "year": "2026"}
        )
        csrf_token = preview_response.cookies["csrftoken"].value
        post_data = {"month": "10", "year": "2026"}
        self.assertEqual(csrf_client.post(management_url, post_data).status_code, 403)
        generated_response = csrf_client.post(
            management_url,
            post_data,
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(generated_response.status_code, 302)
        self.assertEqual(MonthlyCharge.objects.count(), 1)

        staff_user = User.objects.create_user("viewer@example.com", "Safe-viewer-92!")
        staff_user.is_staff = True
        staff_user.save(update_fields=("is_staff",))
        charge_content_type = ContentType.objects.get_for_model(MonthlyCharge)
        view_charge_permission = Permission.objects.get(
            content_type=charge_content_type,
            codename="view_monthlycharge",
        )
        staff_user.user_permissions.add(view_charge_permission)
        self.client.force_login(staff_user)
        viewer_response = self.client.get(
            management_url, {"month": "10", "year": "2026"}
        )
        self.assertEqual(viewer_response.status_code, 200)
        self.assertNotContains(viewer_response, "Generar mensualidades faltantes")
        self.assertEqual(
            self.client.post(management_url, post_data).status_code,
            403,
        )
