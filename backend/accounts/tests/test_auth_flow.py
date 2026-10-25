import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

PASSWORD = "Safe-test-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class SessionAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("dancer@example.com", PASSWORD)
        self.client = APIClient(enforce_csrf_checks=True)
        response = self.client.get("/api/v1/auth/csrf")
        self.assertEqual(response.status_code, 200)
        self.csrf_token = response.json()["csrfToken"]

    def test_login_requires_csrf_and_reports_invalid_credentials_generically(self):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "dancer@example.com", "password": "wrong"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "other@example.com", "password": "wrong"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(), {"detail": "El email o la contraseña no son correctos."}
        )

    def test_login_me_logout_and_cookie_attributes(self):
        response = self.client.post(
            "/api/v1/auth/login",
            data=json.dumps({"email": "DANCER@example.com", "password": PASSWORD}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", response.cookies)
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.assertEqual(response.cookies["sessionid"]["samesite"], "Lax")
        self.assertTrue(response.cookies["csrftoken"]["httponly"])

        response = self.client.get("/api/v1/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], self.user.email)
        self.assertEqual(response["Cache-Control"], "no-store")

        csrf_response = self.client.get("/api/v1/auth/csrf")
        response = self.client.post(
            "/api/v1/auth/logout",
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_response.json()["csrfToken"],
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["sessionid"]["max-age"] == 0)
        self.assertIn(self.client.get("/api/v1/me").status_code, (401, 403))

    def test_authenticated_state_changes_reject_bad_csrf_origin(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/v1/auth/logout",
            data="{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
            HTTP_ORIGIN="http://attacker.example",
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/v1/me").status_code, 200)

    def test_current_user_requires_session(self):
        response = self.client.get("/api/v1/me")
        self.assertIn(response.status_code, (401, 403))
