from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academy.models import Discipline, Enrollment, Student
from accounts.email_verification import create_verification_token
from accounts.invitations import (
    InvalidInvitation,
    InvitationAlreadyPending,
    accept_student_invitation,
    issue_student_invitation,
)
from accounts.models import AccountInvitation
from billing.models import DisciplinePrice, MonthlyCharge

User = get_user_model()
PASSWORD = "Student-link-safe-passphrase-91!"


@override_settings(
    ALLOWED_HOSTS=["testserver", "localhost"],
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FRONTEND_BASE_URL="http://localhost:3000",
)
class StudentInvitationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.issuer = User.objects.create_user("issuer@example.com", PASSWORD)
        self.student = Student.objects.create(
            first_name="Juan", last_name="Cianci", date_of_birth=date(2010, 5, 4)
        )
        self.discipline = Discipline.objects.create(name="Jazz")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrolled_at=date(2026, 9, 1),
        )
        self.price = DisciplinePrice.objects.create(
            discipline=self.discipline,
            effective_month=date(2026, 9, 1),
            amount=Decimal("30000.00"),
        )
        self.charge = MonthlyCharge.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrollment=self.enrollment,
            period=date(2026, 9, 1),
            price_applied=self.price,
            amount=Decimal("30000.00"),
        )

    def create_invitation(self, email="juan@example.com"):
        return issue_student_invitation(
            student_id=self.student.pk,
            email=email,
            created_by=self.issuer,
        )

    def test_new_account_verifies_and_accepts_without_recreating_academic_records(self):
        invitation, token = self.create_invitation()
        response = self.client.post(
            reverse("invitation-activate"),
            {
                "token": token,
                "email": "juan@example.com",
                "firstName": "Juan",
                "lastName": "Cianci",
                "password": PASSWORD,
                "passwordConfirmation": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="juan@example.com")
        invitation.refresh_from_db()
        self.assertIsNone(invitation.consumed_at)
        self.assertIsNone(invitation.accepted_by_id)
        self.assertIsNone(self.student.user_id)

        verification_response = self.client.post(
            reverse("email-verification-confirm"),
            {"token": create_verification_token(user)},
            format="json",
        )
        self.assertEqual(verification_response.status_code, 200)
        listed = self.client.get(reverse("student-invitations"))
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(listed.json()["emailVerified"])
        self.assertEqual(listed.json()["invitations"][0]["studentName"], "Juan Cianci")

        accepted = self.client.post(
            reverse("student-invitation-accept", args=(invitation.pk,)),
            {"student_id": 999999},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200)
        self.student.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(self.student.user_id, user.pk)
        self.assertEqual(invitation.accepted_by_id, user.pk)
        self.assertIsNotNone(invitation.consumed_at)
        self.assertEqual(Enrollment.objects.filter(student=self.student).count(), 1)
        self.assertEqual(MonthlyCharge.objects.filter(student=self.student).count(), 1)
        self.assertEqual(
            self.client.get(reverse("academic-my-students")).json()["count"], 1
        )
        self.assertEqual(
            self.client.get(reverse("billing-my-charges")).json()["count"], 1
        )
        replay = self.client.post(
            reverse("student-invitation-accept", args=(invitation.pk,)),
            {},
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

    def test_existing_verified_account_can_accept_and_other_emails_cannot(self):
        invitation, _ = self.create_invitation("existing@example.com")
        recipient = User.objects.create_user(
            "existing@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        self.client.force_login(recipient)
        self.assertEqual(
            self.client.get(reverse("student-invitations")).json()["invitations"][0]["id"],
            invitation.pk,
        )
        accepted = self.client.post(
            reverse("student-invitation-accept", args=(invitation.pk,)),
            {},
            format="json",
        )
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(User.objects.count(), 2)
        self.student.refresh_from_db()
        self.assertEqual(self.student.user_id, recipient.pk)

    def test_academic_activation_rejects_a_different_email(self):
        _invitation, token = self.create_invitation("juan@example.com")
        response = self.client.post(
            reverse("invitation-activate"),
            {
                "token": token,
                "email": "someone-else@example.com",
                "firstName": "Juan",
                "lastName": "Cianci",
                "password": PASSWORD,
                "passwordConfirmation": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="someone-else@example.com").exists())
        self.assertIsNone(self.student.user_id)


    def test_unverified_wrong_email_expired_and_replayed_accepts_are_rejected(self):
        invitation, _ = self.create_invitation()
        unverified = User.objects.create_user("juan@example.com", PASSWORD)
        self.client.force_login(unverified)
        response = self.client.post(
            reverse("student-invitation-accept", args=(invitation.pk,)),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        wrong_user = User.objects.create_user(
            "wrong@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        self.client.force_login(wrong_user)
        self.assertEqual(
            self.client.get(reverse("student-invitations")).json()["invitations"], []
        )
        self.assertEqual(
            self.client.post(
                reverse("student-invitation-accept", args=(invitation.pk,)),
                {},
                format="json",
            ).status_code,
            400,
        )

        self.client.force_login(unverified)
        unverified.email_verified_at = timezone.now()
        unverified.save(update_fields=("email_verified_at",))
        AccountInvitation.objects.filter(pk=invitation.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        self.assertEqual(
            self.client.post(
                reverse("student-invitation-accept", args=(invitation.pk,)),
                {},
                format="json",
            ).status_code,
            400,
        )

    def test_account_already_linked_to_another_student_is_rejected(self):
        invitation, _ = self.create_invitation("already-linked@example.com")
        user = User.objects.create_user(
            "already-linked@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        other_student = Student.objects.create(
            first_name="Otra", last_name="Persona", user=user
        )
        self.client.force_login(user)
        response = self.client.post(
            reverse("student-invitation-accept", args=(invitation.pk,)),
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("otro alumno", response.json()["detail"])
        self.assertEqual(other_student.user_id, user.pk)
        self.assertIsNone(self.student.user_id)

    def test_pending_invite_is_unique_and_cancellation_is_audited(self):
        invitation, _ = self.create_invitation()
        with self.assertRaises(InvitationAlreadyPending):
            self.create_invitation("other@example.com")
        another_student = Student.objects.create(
            first_name="Ana", last_name="Cianci"
        )
        with self.assertRaises(InvitationAlreadyPending):
            issue_student_invitation(
                student_id=another_student.pk,
                email="juan@example.com",
                created_by=self.issuer,
            )
        invitation.revoked_at = timezone.now()
        invitation.revoked_by = self.issuer
        invitation.revocation_reason = "Cancelada por prueba."
        invitation.save(update_fields=("revoked_at", "revoked_by", "revocation_reason"))
        replacement, _ = self.create_invitation("other@example.com")
        self.assertEqual(replacement.created_by_id, self.issuer.pk)
        invitation.refresh_from_db()
        self.assertEqual(invitation.revoked_by_id, self.issuer.pk)
        self.assertEqual(invitation.revocation_reason, "Cancelada por prueba.")
        self.assertEqual(len(mail.outbox), 0)


class StudentInvitationConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_two_accepts_of_one_invitation_create_one_link(self):
        issuer = User.objects.create_user("issuer@example.com", PASSWORD)
        user = User.objects.create_user(
            "juan@example.com", PASSWORD, email_verified_at=timezone.now()
        )
        student = Student.objects.create(first_name="Juan", last_name="Cianci")
        invitation, _ = issue_student_invitation(
            student_id=student.pk,
            email=user.email,
            created_by=issuer,
        )
        barrier = Barrier(2)

        def accept():
            from django.db import close_old_connections

            close_old_connections()
            try:
                locked_user = User.objects.get(pk=user.pk)
                barrier.wait(timeout=5)
                accept_student_invitation(
                    invitation_id=invitation.pk,
                    user=locked_user,
                )
                return "accepted"
            except InvalidInvitation:
                return "rejected"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: accept(), range(2)))

        self.assertEqual(results.count("accepted"), 1)
        student.refresh_from_db()
        invitation.refresh_from_db()
        self.assertEqual(student.user_id, user.pk)
        self.assertEqual(invitation.accepted_by_id, user.pk)
        self.assertIsNotNone(invitation.consumed_at)

    def test_two_concurrent_issues_leave_one_pending_invitation(self):
        issuer = User.objects.create_user("issuer@example.com", PASSWORD)
        student = Student.objects.create(first_name="Juan", last_name="Cianci")
        barrier = Barrier(2)

        def issue(index):
            from django.db import close_old_connections

            close_old_connections()
            try:
                locked_issuer = User.objects.get(pk=issuer.pk)
                barrier.wait(timeout=5)
                issue_student_invitation(
                    student_id=student.pk,
                    email=f"juan{index}@example.com",
                    created_by=locked_issuer,
                )
                return "created"
            except InvitationAlreadyPending:
                return "already_pending"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(issue, range(2)))

        self.assertEqual(results.count("created"), 1)
        self.assertEqual(results.count("already_pending"), 1)
        self.assertEqual(
            AccountInvitation.objects.filter(
                student=student,
                consumed_at__isnull=True,
                revoked_at__isnull=True,
            ).count(),
            1,
        )
