import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.invitations import activate_invitation, issue_invitation
from accounts.models import AccountInvitation

User = get_user_model()
PASSWORD = "Fuchsia-Forest-Zebra-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class InvitationFlowTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            "invitation-admin@example.com", "Test-admin-passphrase-91!"
        )
        self.invitation, self.token = issue_invitation(
            email="Invitee@EXAMPLE.com",
            first_name="Ada",
            last_name="Cianci",
            expires_at=timezone.now() + timedelta(days=2),
            created_by=self.admin_user,
        )
        self.client = Client(enforce_csrf_checks=True)
        csrf_response = self.client.get("/api/v1/auth/csrf")
        self.csrf_token = csrf_response.json()["csrfToken"]

    def post_json(self, path, payload, *, csrf=True):
        headers = {"HTTP_ORIGIN": "http://localhost:3000"}
        if csrf:
            headers["HTTP_X_CSRFTOKEN"] = self.csrf_token
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def activation_payload(self, **overrides):
        payload = {
            "token": self.token,
            "email": "invitee@example.com",
            "firstName": "Ada",
            "lastName": "Cianci",
            "password": PASSWORD,
            "passwordConfirmation": PASSWORD,
        }
        payload.update(overrides)
        return payload

    def test_only_token_hash_is_stored_and_inspection_returns_invited_data(self):
        self.assertNotEqual(self.invitation.token_hash, self.token)
        self.assertEqual(len(self.invitation.token_hash), 64)

        response = self.post_json(
            "/api/v1/auth/invitations/inspect", {"token": self.token}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "email": "invitee@example.com",
                "emailBound": True,
                "firstName": "Ada",
                "lastName": "Cianci",
            },
        )
        self.assertIn("no-store", response["Cache-Control"])

    def test_activation_creates_user_consumes_invitation_and_starts_session(self):
        response = self.post_json(
            "/api/v1/auth/invitations/activate", self.activation_payload()
        )

        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="invitee@example.com")
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual((user.first_name, user.last_name), ("Ada", "Cianci"))
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.consumed_at)
        self.assertEqual(self.invitation.claimed_user, user)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verificar-email#", mail.outbox[0].body)

        self.csrf_token = self.client.get("/api/v1/auth/csrf").json()["csrfToken"]
        retry = self.post_json(
            "/api/v1/auth/invitations/activate", self.activation_payload()
        )
        self.assertEqual(retry.status_code, 400)
        self.assertEqual(User.objects.filter(email="invitee@example.com").count(), 1)

    def test_smtp_failure_does_not_fail_invitation_activation(self):
        with patch("accounts.email_verification.send_mail", side_effect=OSError):
            response = self.post_json(
                "/api/v1/auth/invitations/activate", self.activation_payload()
            )
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="invitee@example.com")
        self.assertIsNone(user.email_verified_at)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)

    def test_email_binding_csrf_and_existing_account_are_enforced(self):
        missing_csrf = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(email="other@example.com"),
            csrf=False,
        )
        self.assertEqual(missing_csrf.status_code, 403)

        mismatch = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(email="other@example.com"),
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

        User.objects.create_user("existing@example.com", PASSWORD)
        unbound, unbound_token = issue_invitation(
            email=None,
            first_name="",
            last_name="",
            expires_at=timezone.now() + timedelta(days=2),
            created_by=self.admin_user,
        )
        response = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(token=unbound_token, email="existing@example.com"),
        )
        self.assertEqual(response.status_code, 400)
        unbound.refresh_from_db()
        self.assertIsNone(unbound.consumed_at)
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)

    def test_expired_revoked_and_authenticated_claims_are_rejected(self):
        expired, expired_token = issue_invitation(
            email=None,
            first_name="",
            last_name="",
            expires_at=timezone.now() + timedelta(minutes=1),
            created_by=self.admin_user,
        )
        AccountInvitation.objects.filter(pk=expired.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        response = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(token=expired_token),
        )
        self.assertEqual(response.status_code, 400)

        revoked, revoked_token = issue_invitation(
            email=None,
            first_name="",
            last_name="",
            expires_at=timezone.now() + timedelta(days=1),
            created_by=self.admin_user,
        )
        revoked.revoked_at = timezone.now()
        revoked.revoked_by = self.admin_user
        revoked.save(update_fields=("revoked_at", "revoked_by"))
        response = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(token=revoked_token),
        )
        self.assertEqual(response.status_code, 400)

        self.client.force_login(self.admin_user)
        response = self.post_json(
            "/api/v1/auth/invitations/activate",
            self.activation_payload(token=self.token),
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_can_create_copy_and_revoke_invitation(self):
        admin_client = Client()
        admin_client.force_login(self.admin_user)
        add_url = reverse("admin:accounts_accountinvitation_add")
        response = admin_client.get(add_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crear invitación")

        expires_at = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        response = admin_client.post(
            add_url,
            {
                "email": "admin-created@example.com",
                "first_name": "Ballet",
                "last_name": "Cianci",
                "expires_at": expires_at,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Copiar enlace")
        self.assertIn("no-store", response["Cache-Control"])
        match = re.search(r"/activar#([A-Za-z0-9_-]+)", response.content.decode())
        self.assertIsNotNone(match)
        invitation = AccountInvitation.objects.get(email="admin-created@example.com")
        self.assertNotEqual(invitation.token_hash, match.group(1))

        response = admin_client.post(
            reverse("admin:accounts_accountinvitation_changelist"),
            {
                "action": "revoke_invitations",
                "_selected_action": [invitation.pk],
                "index": 0,
            },
        )
        self.assertEqual(response.status_code, 302)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.revoked_at)
        self.assertEqual(invitation.revoked_by, self.admin_user)

    def test_failure_while_consuming_rolls_back_created_user(self):
        original_save = AccountInvitation.save

        def fail_consumption(invitation, *args, **kwargs):
            if invitation.consumed_at is not None:
                raise RuntimeError("simulated database failure")
            return original_save(invitation, *args, **kwargs)

        with patch.object(AccountInvitation, "save", fail_consumption):
            with self.assertRaisesMessage(RuntimeError, "simulated database failure"):
                activate_invitation(
                    token=self.token,
                    email="invitee@example.com",
                    first_name="Ada",
                    last_name="Cianci",
                    password=PASSWORD,
                )

        self.assertFalse(User.objects.filter(email="invitee@example.com").exists())
        self.invitation.refresh_from_db()
        self.assertIsNone(self.invitation.consumed_at)
        self.assertIsNone(self.invitation.claimed_user_id)


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ConcurrentInvitationActivationTests(TransactionTestCase):
    reset_sequences = True

    def test_simultaneous_claims_consume_token_once(self):
        admin_user = User.objects.create_superuser(
            "concurrent-admin@example.com", "Test-admin-passphrase-91!"
        )
        invitation, token = issue_invitation(
            email="simultaneous@example.com",
            first_name="",
            last_name="",
            expires_at=timezone.now() + timedelta(days=1),
            created_by=admin_user,
        )
        clients = [Client(enforce_csrf_checks=True) for _ in range(2)]
        csrf_tokens = [
            client.get("/api/v1/auth/csrf").json()["csrfToken"] for client in clients
        ]
        barrier = threading.Barrier(2)

        def activate(client, csrf_token):
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                return client.post(
                    "/api/v1/auth/invitations/activate",
                    data=json.dumps(
                        {
                            "token": token,
                            "email": "simultaneous@example.com",
                            "firstName": "",
                            "lastName": "",
                            "password": PASSWORD,
                            "passwordConfirmation": PASSWORD,
                        }
                    ),
                    content_type="application/json",
                    HTTP_X_CSRFTOKEN=csrf_token,
                    HTTP_ORIGIN="http://localhost:3000",
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(
                executor.map(
                    lambda args: activate(*args), zip(clients, csrf_tokens, strict=True)
                )
            )

        self.assertCountEqual(statuses, [201, 400])
        self.assertEqual(
            User.objects.filter(email="simultaneous@example.com").count(), 1
        )
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.consumed_at)
        self.assertIsNotNone(invitation.claimed_user_id)
