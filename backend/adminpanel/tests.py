from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from academy.models import ClassSchedule, Discipline, Enrollment, Student, Teacher
from adminpanel.permissions import (
    ADMIN_PANEL_VIEW_PERMISSIONS,
    INSTITUTE_ADMIN_PERMISSIONS,
)
from billing.models import DisciplinePrice, MonthlyCharge
from payments.models import PaymentIntent

User = get_user_model()
PASSWORD = "Safe-admin-panel-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AdminDashboardAccessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff_user = User.objects.create_user(
            "admin@example.com", PASSWORD, is_staff=True
        )
        self.grant_dashboard_permissions(self.staff_user)

    @staticmethod
    def grant_dashboard_permissions(user):
        for permission_name in ADMIN_PANEL_VIEW_PERMISSIONS:
            app_label, codename = permission_name.split(".")
            user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )

    def test_authorized_staff_receives_private_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            set(response.json()),
            {
                "date",
                "activeStudents",
                "outstandingAmount",
                "pendingTransfers",
                "recurringSchedulesToday",
                "links",
            },
        )

    def test_superuser_can_access_without_explicit_model_permissions(self):
        superuser = User.objects.create_superuser("owner@example.com", PASSWORD)
        self.client.force_login(superuser)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_without_permissions_is_denied(self):
        user = User.objects.create_user("student@example.com", PASSWORD)
        self.client.force_login(user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_staff_flag_alone_does_not_authorize_dashboard(self):
        user = User.objects.create_user(
            "unprivileged-staff@example.com", PASSWORD, is_staff=True
        )
        self.client.force_login(user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_missing_one_read_permission_revokes_dashboard_access(self):
        permission_name = ADMIN_PANEL_VIEW_PERMISSIONS[0]
        app_label, codename = permission_name.split(".")
        self.staff_user.user_permissions.remove(
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_denied(self):
        response = self.client.get(reverse("admin-dashboard"))

        self.assertIn(response.status_code, (401, 403))

    def test_dashboard_indicators_use_current_domain_data(self):
        today = date(2026, 10, 26)
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        discipline = Discipline.objects.create(name="Jazz")
        Enrollment.objects.create(student=student, discipline=discipline)
        teacher = Teacher.objects.create(first_name="Loli", last_name="Fernández")
        ClassSchedule.objects.create(
            discipline=discipline,
            teacher=teacher,
            weekday=today.weekday(),
            start_time="18:00",
            end_time="19:00",
        )
        price = DisciplinePrice.objects.create(
            discipline=discipline,
            amount="30000.00",
            effective_month=today.replace(day=1),
        )
        enrollment = Enrollment.objects.get(student=student)
        MonthlyCharge.objects.create(
            student=student,
            discipline=discipline,
            enrollment=enrollment,
            period=today.replace(day=1),
            price_applied=price,
            base_amount="30000.00",
            discount_amount="0.00",
            amount="30000.00",
        )
        PaymentIntent.objects.create(
            student=student,
            amount="10000.00",
            created_by=self.staff_user,
        )
        self.client.force_login(self.staff_user)

        with patch("adminpanel.queries.timezone.localdate", return_value=today):
            response = self.client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["activeStudents"], 1)
        self.assertEqual(response.json()["outstandingAmount"], "30000.00")
        self.assertEqual(response.json()["pendingTransfers"], 1)
        self.assertEqual(response.json()["recurringSchedulesToday"], 1)

    def test_current_user_response_only_exposes_panel_capability_boolean(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse("current-user"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["canAccessAdminPanel"])
        self.assertEqual(response["Cache-Control"], "no-store")

        user_without_access = User.objects.create_user("family@example.com", PASSWORD)
        self.client.force_login(user_without_access)
        response = self.client.get(reverse("current-user"))
        self.assertFalse(response.json()["canAccessAdminPanel"])


class InstituteAdministratorGroupTests(TestCase):
    def test_group_command_is_repeatable_and_does_not_assign_users(self):
        user = User.objects.create_user("ema@example.com", PASSWORD, is_staff=True)

        call_command("sync_institute_admin_group")
        call_command("sync_institute_admin_group")

        group = Group.objects.get(name="Institute Administrator")
        actual_permissions = {
            f"{permission.content_type.app_label}.{permission.codename}"
            for permission in group.permissions.all()
        }
        self.assertEqual(actual_permissions, set(INSTITUTE_ADMIN_PERMISSIONS))
        self.assertFalse(group.user_set.filter(pk=user.pk).exists())
        self.assertNotIn("accounts.change_user", actual_permissions)
        self.assertNotIn("auth.change_group", actual_permissions)
        self.assertNotIn("auth.change_permission", actual_permissions)

        user.groups.add(group)
        client = APIClient()
        client.force_login(user)
        response = client.get(reverse("admin-dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["links"]["guardians"])
        self.assertTrue(response.json()["links"]["chargeGeneration"])
        self.assertTrue(response.json()["links"]["transfers"])
        self.assertTrue(response.json()["links"]["canResolveTransfers"])
        self.assertTrue(response.json()["links"]["payments"])
