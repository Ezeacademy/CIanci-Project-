import json
import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from accounts.email_verification import create_verification_token

PASSWORD = "Safe-test-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class EmailAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "dancer@example.com", PASSWORD
        )
        self.client = APIClient(enforce_csrf_checks=True)
        self.csrf_token = self.client.get("/api/v1/auth/csrf").json()["csrfToken"]

    def post(self, path, data):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="http://localhost:3000",
        )

    def test_password_reset_is_generic_and_email_is_native(self):
        response = self.post(
            "/api/v1/auth/password-reset", {"email": self.user.email}
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/restablecer#", mail.outbox[0].body)
        unknown = self.post(
            "/api/v1/auth/password-reset", {"email": "missing@example.com"}
        )
        self.assertEqual((unknown.status_code, unknown.json()), (202, response.json()))
        self.assertEqual(len(mail.outbox), 1)

    def test_anonymous_email_actions_require_csrf(self):
        response = self.client.post(
            "/api/v1/auth/password-reset",
            data=json.dumps({"email": self.user.email}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

    def test_password_reset_changes_password_and_invalidates_old_session_and_token(
        self,
    ):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.client.force_login(self.user)
        self.user.refresh_from_db()
        token = default_token_generator.make_token(self.user)
        response = self.post(
            "/api/v1/auth/password-reset/confirm",
            {
                "uid": uid,
                "token": token,
                "password": "Another-safe-passphrase-74!",
                "passwordConfirmation": "Another-safe-passphrase-74!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-safe-passphrase-74!"))
        self.assertIsNone(self.user.email_verified_at)
        self.assertIn(self.client.get("/api/v1/me").status_code, (401, 403))
        repeat = self.post(
            "/api/v1/auth/password-reset/confirm",
            {
                "uid": uid,
                "token": token,
                "password": "Yet-another-safe-passphrase-79!",
                "passwordConfirmation": "Yet-another-safe-passphrase-79!",
            },
        )
        self.assertEqual(repeat.status_code, 400)

    def test_password_validators_reject_weak_password(self):
        response = self.post(
            "/api/v1/auth/password-reset/confirm",
            {
                "uid": urlsafe_base64_encode(force_bytes(self.user.pk)),
                "token": default_token_generator.make_token(self.user),
                "password": "123",
                "passwordConfirmation": "123",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_verification_is_idempotent_and_email_change_invalidates_link(self):
        token = create_verification_token(self.user)
        first = self.post(
            "/api/v1/auth/email-verification/confirm", {"token": token}
        )
        second = self.post(
            "/api/v1/auth/email-verification/confirm", {"token": token}
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.user.refresh_from_db()
        verified_at = self.user.email_verified_at
        self.assertIsNotNone(verified_at)
        self.user.email = "changed@example.com"
        self.user.save(update_fields=["email"])
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_verified_at)
        stale = self.post(
            "/api/v1/auth/email-verification/confirm", {"token": token}
        )
        self.assertEqual(stale.status_code, 400)

    @override_settings(EMAIL_VERIFICATION_TIMEOUT=-1)
    def test_expired_verification_token_is_rejected(self):
        token = create_verification_token(self.user)
        response = self.post(
            "/api/v1/auth/email-verification/confirm", {"token": token}
        )
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertIsNone(self.user.email_verified_at)

    def test_verification_resend_requires_login_and_smtp_failure_is_generic(self):
        self.assertEqual(
            self.post("/api/v1/auth/email-verification/resend", {}).status_code,
            403,
        )
        self.client.force_login(self.user)
        with patch("accounts.email_verification.send_mail", side_effect=OSError):
            response = self.post("/api/v1/auth/email-verification/resend", {})
        self.assertEqual(response.status_code, 200)
        self.assertIn("recibirás", response.json()["detail"])


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class ConcurrentPasswordResetTests(TransactionTestCase):
    def test_a_reset_token_succeeds_only_once_under_concurrent_requests(self):
        user = get_user_model().objects.create_user("race@example.com", PASSWORD)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        barrier = threading.Barrier(2)

        def reset(password):
            close_old_connections()
            client = APIClient(enforce_csrf_checks=True)
            csrf_token = client.get("/api/v1/auth/csrf").json()["csrfToken"]
            barrier.wait(timeout=10)
            response = client.post(
                "/api/v1/auth/password-reset/confirm",
                data=json.dumps(
                    {
                        "uid": uid,
                        "token": token,
                        "password": password,
                        "passwordConfirmation": password,
                    }
                ),
                content_type="application/json",
                HTTP_X_CSRFTOKEN=csrf_token,
                HTTP_ORIGIN="http://localhost:3000",
            )
            close_old_connections()
            return response.status_code

        passwords = ("Concurrent-safe-password-83!", "Concurrent-safe-password-84!")
        with ThreadPoolExecutor(max_workers=2) as executor:
            statuses = list(executor.map(reset, passwords))

        self.assertEqual(sorted(statuses), [200, 400])
        user.refresh_from_db()
        self.assertTrue(any(user.check_password(password) for password in passwords))
