from unittest.mock import patch

from django.apps import apps
from django.db import OperationalError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
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

    def test_auth_apps_and_migrations_are_not_enabled(self):
        self.assertIsNone(api_settings.UNAUTHENTICATED_USER)
        self.assertEqual(api_settings.DEFAULT_AUTHENTICATION_CLASSES, [])
        for label in ("auth", "admin", "sessions"):
            self.assertFalse(apps.is_installed(f"django.contrib.{label}"))
        tables = connection.introspection.table_names()
        self.assertNotIn("auth_user", tables)
        self.assertNotIn("django_session", tables)
        migrated_apps = {
            app for app, _ in MigrationExecutor(connection).loader.graph.nodes
        }
        self.assertTrue(migrated_apps.isdisjoint({"auth", "admin", "sessions"}))
