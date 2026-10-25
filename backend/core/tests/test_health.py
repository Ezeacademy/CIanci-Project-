from unittest.mock import patch

from django.db import OperationalError, connection
from django.test import TestCase
from django.urls import resolve
from rest_framework.authentication import SessionAuthentication
from rest_framework.settings import api_settings
from rest_framework.test import APIClient


class HealthTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_health_checks_real_postgresql_without_credentials(self):
        self.assertEqual(connection.vendor, "postgresql")
        with self.assertNumQueries(1):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_database_failure_is_sanitized(self):
        with patch(
            "core.views.connection.cursor", side_effect=OperationalError("secret")
        ):
            response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotContains(response, "secret", status_code=503)

    def test_write_methods_are_not_allowed(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    "/api/v1/health/", {}, format="json"
                )
                self.assertEqual(response.status_code, 405)

    def test_api_uses_sessions_and_healthcheck_remains_public(self):
        self.assertIsNone(api_settings.UNAUTHENTICATED_USER)
        self.assertEqual(
            api_settings.DEFAULT_AUTHENTICATION_CLASSES, [SessionAuthentication]
        )
        self.assertEqual(resolve("/api/v1/health/").func.cls.authentication_classes, [])
