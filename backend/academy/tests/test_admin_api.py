from unittest.mock import Mock, patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship

User = get_user_model()
PASSWORD = "Safe-academic-admin-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AdminAcademicAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            "manager@example.com", PASSWORD, is_staff=True
        )
        self.grant(
            self.staff,
            "academy.view_student",
            "academy.add_student",
            "academy.change_student",
            "academy.view_enrollment",
            "academy.add_enrollment",
            "academy.change_enrollment",
            "academy.view_discipline",
            "academy.invite_student_account",
            "accounts.view_guardianrelationship",
            "billing.add_monthlycharge",
        )
        self.client.force_login(self.staff)
        self.list_url = reverse("admin-academic-students")
        self.discipline = Discipline.objects.create(name="Jazz")

    @staticmethod
    def grant(user_or_group, *permissions):
        relation = (
            user_or_group.permissions
            if isinstance(user_or_group, Group)
            else user_or_group.user_permissions
        )
        for permission_name in permissions:
            app_label, codename = permission_name.split(".")
            relation.add(
                Permission.objects.get(
                    content_type__app_label=app_label, codename=codename
                )
            )

    def test_anonymous_and_staff_without_operation_permission_are_denied(self):
        self.client.logout()
        self.assertIn(self.client.get(self.list_url).status_code, (401, 403))
        self.client.force_login(
            User.objects.create_user("other@example.com", PASSWORD, is_staff=True)
        )
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(
            self.client.post(
                self.list_url,
                {"first_name": "Ada", "last_name": "Luz"},
                format="json",
            ).status_code,
            403,
        )

    def test_superuser_can_access_staff_endpoint_without_explicit_model_permissions(
        self,
    ):
        owner = User.objects.create_superuser("owner@example.com", PASSWORD)
        self.client.force_login(owner)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)

    def test_authorized_group_grants_access_to_the_academic_list(self):
        group = Group.objects.create(name="Academic test group")
        self.grant(
            group,
            "academy.view_student",
            "academy.view_enrollment",
            "academy.view_discipline",
        )
        manager = User.objects.create_user(
            "group-manager@example.com", PASSWORD, is_staff=True
        )
        manager.groups.add(group)
        self.client.force_login(manager)

        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, 200)

    def test_student_list_search_filters_and_pagination_are_server_side(self):
        target = Student.objects.create(first_name="Candela", last_name="Manzo")
        Enrollment.objects.create(student=target, discipline=self.discipline)
        for index in range(21):
            Student.objects.create(first_name=f"Alumno {index:02}", last_name="Prueba")

        first_page = self.client.get(self.list_url)
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page["Cache-Control"], "no-store")
        self.assertEqual(first_page.json()["count"], 22)
        self.assertEqual(len(first_page.json()["results"]), 20)

        search = self.client.get(self.list_url, {"q": "candela manzo"})
        self.assertEqual([row["id"] for row in search.json()["results"]], [target.pk])
        active = self.client.get(self.list_url, {"status": "active"})
        self.assertEqual([row["id"] for row in active.json()["results"]], [target.pk])
        by_discipline = self.client.get(
            self.list_url, {"discipline": self.discipline.pk}
        )
        self.assertEqual(
            [row["id"] for row in by_discipline.json()["results"]], [target.pk]
        )

    def test_create_student_does_not_link_account_and_rejects_protected_fields(self):
        response = self.client.post(
            self.list_url,
            {
                "first_name": "  Ada ",
                "last_name": "Luz",
                "date_of_birth": "2012-03-04",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()["canInviteStudentAccount"])
        student = Student.objects.get(pk=response.json()["id"])
        self.assertEqual(student.first_name, "Ada")
        self.assertIsNone(student.user_id)
        self.assertTrue(
            LogEntry.objects.filter(object_id=str(student.pk), user=self.staff).exists()
        )

        protected = self.client.post(
            self.list_url,
            {"first_name": "No", "last_name": "Link", "user": self.staff.pk},
            format="json",
        )
        self.assertEqual(protected.status_code, 400)

    def test_student_edit_accepts_only_editable_fields(self):
        student = Student.objects.create(first_name="Alba", last_name="Prueba")
        url = reverse("admin-academic-student-detail", args=(student.pk,))
        changed = self.client.patch(url, {"last_name": "Nueva"}, format="json")
        self.assertEqual(changed.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.last_name, "Nueva")
        rejected = self.client.patch(url, {"user": self.staff.pk}, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertIsNone(student.user_id)

    def test_detail_shows_guardian_name_but_never_email_or_account_fields(self):
        student = Student.objects.create(first_name="Eva", last_name="Prueba")
        guardian = User.objects.create_user(
            "private-guardian@example.com",
            PASSWORD,
            first_name="Rosa",
            last_name="Paz",
        )
        GuardianRelationship.objects.create(
            guardian=guardian, student=student, created_by=self.staff
        )
        response = self.client.get(
            reverse("admin-academic-student-detail", args=(student.pk,))
        )
        payload = response.json()
        self.assertEqual(payload["guardians"], [{"name": "Rosa Paz", "isActive": True}])
        self.assertNotIn("private-guardian@example.com", str(payload))
        self.assertNotIn("user", payload)

    def test_enrollment_creation_and_finish_keep_history_and_are_not_replayable(self):
        student = Student.objects.create(first_name="Cande", last_name="Manzo")
        create_url = reverse("admin-academic-enrollment-create", args=(student.pk,))
        with patch("academy.services.generate_monthly_charges") as generate:
            generate.return_value = Mock(created=0, missing_prices=(), existing=1)
            response = self.client.post(
                create_url,
                {
                    "discipline_id": self.discipline.pk,
                    "enrolled_at": timezone.localdate().isoformat(),
                },
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        enrollment = Enrollment.objects.get(pk=response.json()["id"])
        self.assertEqual(response.json()["initialChargeStatus"], "already_exists")
        generate.assert_called_once()

        duplicate = self.client.post(
            create_url,
            {
                "discipline_id": self.discipline.pk,
                "enrolled_at": timezone.localdate().isoformat(),
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

        finish_url = reverse(
            "admin-academic-enrollment-finish", args=(student.pk, enrollment.pk)
        )
        finished = self.client.post(finish_url, {}, format="json")
        self.assertEqual(finished.status_code, 200)
        enrollment.refresh_from_db()
        self.assertIsNotNone(enrollment.ended_at)
        replayed = self.client.post(finish_url, {}, format="json")
        self.assertEqual(replayed.status_code, 400)
        self.assertEqual(Enrollment.objects.count(), 1)

        with patch("academy.services.generate_monthly_charges") as generate:
            generate.return_value = Mock(created=0, missing_prices=(), existing=1)
            reenrolled = self.client.post(
                create_url,
                {
                    "discipline_id": self.discipline.pk,
                    "enrolled_at": timezone.localdate().isoformat(),
                },
                format="json",
            )
        self.assertEqual(reenrolled.status_code, 201)
        self.assertEqual(Enrollment.objects.count(), 2)
        self.assertEqual(
            Enrollment.objects.filter(student=student, ended_at__isnull=True).count(),
            1,
        )

    def test_revoking_permission_denies_direct_operation(self):
        self.staff.user_permissions.remove(
            Permission.objects.get(
                content_type__app_label="academy", codename="add_student"
            )
        )
        response = self.client.post(
            self.list_url,
            {"first_name": "Ada", "last_name": "Luz"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Student.objects.count(), 0)
