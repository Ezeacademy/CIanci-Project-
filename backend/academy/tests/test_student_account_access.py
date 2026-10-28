from datetime import date
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academy.models import Student
from accounts.models import AccountInvitation

User = get_user_model()
PASSWORD = "Student-access-admin-passphrase-91!"


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_BASE_URL="http://localhost:3000",
)
class StudentAccountInvitationAdminAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            "manager@example.com", PASSWORD, is_staff=True
        )
        self.student = Student.objects.create(
            first_name="Juan", last_name="Cianci", date_of_birth=date(2010, 5, 4)
        )
        self.create_url = reverse(
            "admin-academic-student-invitation-create", args=(self.student.pk,)
        )
        self.client.force_login(self.manager)

    def grant(self, user, *codenames):
        for codename in codenames:
            user.user_permissions.add(
                Permission.objects.get(
                    content_type__app_label="academy", codename=codename
                )
            )

    def test_permissioned_invitation_is_email_bound_audited_and_never_returns_token(
        self,
    ):
        denied = self.client.post(self.create_url, {"email": "juan@example.com"})
        self.assertEqual(denied.status_code, 403)

        self.grant(self.manager, "invite_student_account")
        response = self.client.post(self.create_url, {"email": " Juan@Example.com "})

        self.assertEqual(response.status_code, 201)
        self.assertNotIn("token", response.json())
        invitation = AccountInvitation.objects.get(student=self.student)
        self.assertEqual(invitation.email, "juan@example.com")
        self.assertIsNotNone(invitation.created_by_id)
        self.assertEqual(invitation.created_by_id, self.manager.pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["juan@example.com"])
        token = mail.outbox[0].body.split("/activar#", 1)[1].split()[0]
        self.assertNotEqual(invitation.token_hash, token)
        self.assertNotIn(token, response.content.decode())
        self.assertTrue(
            LogEntry.objects.filter(
                user=self.manager,
                object_id=str(invitation.pk),
            ).exists()
        )

        duplicate = self.client.post(self.create_url, {"email": "juan@example.com"})
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(
            AccountInvitation.objects.filter(student=self.student).count(), 1
        )
        invitation = AccountInvitation.objects.get(student=self.student)
        cancellation = self.client.post(
            reverse(
                "admin-academic-student-invitation-cancel",
                args=(self.student.pk, invitation.pk),
            ),
            {},
        )
        self.assertEqual(cancellation.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.revoked_by_id, self.manager.pk)
        self.assertTrue(invitation.revocation_reason)

    @patch("academy.admin_api.send_student_invitation_email", return_value=False)
    def test_failed_delivery_is_reported_and_invitation_is_cancelled(self, _send_email):
        self.grant(self.manager, "invite_student_account")
        response = self.client.post(self.create_url, {"email": "juan@example.com"})
        self.assertEqual(response.status_code, 503)
        invitation = AccountInvitation.objects.get(student=self.student)
        self.assertIsNotNone(invitation.revoked_at)
        self.assertEqual(invitation.revoked_by_id, self.manager.pk)

    def test_superuser_uses_django_permission_bypass_and_revoke_is_audited(self):
        owner = User.objects.create_superuser("owner@example.com", PASSWORD)
        recipient = User.objects.create_user(
            "juan@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        self.student.user = recipient
        self.student.save(update_fields=("user", "updated_at"))
        self.client.force_login(owner)
        detail = self.client.get(
            reverse("admin-academic-student-detail", args=(self.student.pk,))
        )
        self.assertEqual(detail.status_code, 200)
        self.assertTrue(detail.json()["canRevokeStudentAccount"])

        revoke = self.client.post(
            reverse("admin-academic-student-account-revoke", args=(self.student.pk,)),
            {},
        )
        self.assertEqual(revoke.status_code, 200)
        self.student.refresh_from_db()
        self.assertIsNone(self.student.user_id)
        self.assertTrue(
            LogEntry.objects.filter(
                user=owner,
                object_id=str(self.student.pk),
                change_message__contains="Acceso del alumno revocado",
            ).exists()
        )

        account_client = APIClient()
        account_client.force_login(recipient)
        private_students = account_client.get(reverse("academic-my-students"))
        self.assertEqual(private_students.status_code, 200)
        self.assertEqual(private_students.json()["results"], [])

    def test_staff_must_have_the_specific_permission_to_revoke_access(self):
        recipient = User.objects.create_user(
            "juan@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        self.student.user = recipient
        self.student.save(update_fields=("user", "updated_at"))
        self.client.force_login(self.manager)
        revoke_url = reverse(
            "admin-academic-student-account-revoke", args=(self.student.pk,)
        )
        self.assertEqual(self.client.post(revoke_url, {}).status_code, 403)

        self.grant(self.manager, "revoke_student_account")
        response = self.client.post(revoke_url, {})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            LogEntry.objects.filter(
                user=self.manager,
                object_id=str(self.student.pk),
                change_message__contains="Acceso del alumno revocado",
            ).exists()
        )

    def test_student_account_field_is_hidden_from_non_superuser_admin_forms(self):
        self.grant(self.manager, "change_student")
        request = RequestFactory().get("/admin/academy/student/")
        request.user = self.manager
        student_admin = admin.site._registry[Student]
        self.assertNotIn("user", student_admin.get_fields(request, self.student))

        owner = User.objects.create_superuser("owner@example.com", PASSWORD)
        request.user = owner
        self.assertIn("user", student_admin.get_fields(request, self.student))

    def test_anonymous_user_cannot_create_or_read_student_invitation_state(self):
        self.client.logout()
        detail_url = reverse("admin-academic-student-detail", args=(self.student.pk,))
        self.assertIn(self.client.get(detail_url).status_code, (401, 403))
        self.assertIn(
            self.client.post(
                self.create_url, {"email": "juan@example.com"}
            ).status_code,
            (401, 403),
        )
