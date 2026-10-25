from io import StringIO
from unittest.mock import patch

from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase
from django.urls import reverse

from accounts.forms import AccountChangeForm, AccountCreationForm

User = get_user_model()
PASSWORD = "Synthetic-test-passphrase-76!"


class IdentityTests(TestCase):
    def test_custom_user_is_in_initial_migration_and_no_default_table(self):
        self.assertEqual(User._meta.label, "accounts.User")
        self.assertEqual(User.USERNAME_FIELD, "email")
        state = MigrationExecutor(connection).loader.project_state(
            [("accounts", "0001_initial")]
        )
        self.assertIn("email", state.models["accounts", "user"].fields)
        self.assertNotIn("username", state.models["accounts", "user"].fields)
        tables = connection.introspection.table_names()
        self.assertIn("accounts_user", tables)
        self.assertNotIn("auth_user", tables)
        self.assertIn("django_session", tables)

    def test_create_user_normalizes_email_and_hashes_password(self):
        user = User.objects.create_user(" Dancer@EXAMPLE.COM ", PASSWORD)
        user.refresh_from_db()
        self.assertEqual(user.email, "dancer@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertEqual(
            authenticate(email="DANCER@example.com", password=PASSWORD), user
        )
        self.assertIsNone(authenticate(email=user.email, password="wrong-password"))

    def test_empty_and_invalid_email_are_rejected(self):
        for email in (None, "", "  "):
            with self.subTest(email=email), self.assertRaises(ValueError):
                User.objects.create_user(email, PASSWORD)
        with self.assertRaises(ValidationError):
            User.objects.create_user("not-an-email", PASSWORD)
        self.assertEqual(User.objects.count(), 0)

    def test_user_without_password_has_unusable_password(self):
        user = User.objects.create_user("inactive-password@example.com")
        self.assertFalse(user.has_usable_password())

    def test_duplicate_email_rejected_by_manager_and_database(self):
        user = User.objects.create_user("same@example.com", PASSWORD)
        with self.assertRaises(ValidationError):
            User.objects.create_user("SAME@example.com", PASSWORD)
        other = User.objects.create_user("other@example.com", PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=other.pk).update(email=user.email.upper())

    def test_create_superuser_flags_and_password(self):
        user = User.objects.create_superuser("ROOT@example.com", PASSWORD)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.email, "root@example.com")

    def test_invalid_superuser_configuration_is_rejected(self):
        for flags in ({"is_staff": False}, {"is_superuser": False}):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                User.objects.create_superuser("root@example.com", PASSWORD, **flags)
        with self.assertRaises(ValueError):
            User.objects.create_superuser("root@example.com")
        self.assertEqual(User.objects.count(), 0)

    def test_createsuperuser_command_uses_email(self):
        with patch.dict("os.environ", {"DJANGO_SUPERUSER_PASSWORD": PASSWORD}):
            call_command(
                "createsuperuser",
                email="cli@example.com",
                interactive=False,
                stdout=StringIO(),
            )
        self.assertTrue(
            User.objects.get(email="cli@example.com").check_password(PASSWORD)
        )

    def test_admin_forms_create_change_and_preserve_password(self):
        form = AccountCreationForm(
            data={
                "email": "FORM@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertTrue(user.check_password(PASSWORD))
        form = AccountChangeForm(
            data={
                "email": "edited@example.com",
                "first_name": "Example",
                "last_name": "",
                "is_active": True,
                "date_joined": user.date_joined,
            },
            instance=user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, "edited@example.com")
        self.assertTrue(user.check_password(PASSWORD))

    def test_admin_creation_rejects_duplicate_email_and_weak_password(self):
        User.objects.create_user("existing@example.com", PASSWORD)
        form = AccountCreationForm(
            data={
                "email": "EXISTING@example.com",
                "password1": PASSWORD,
                "password2": PASSWORD,
            }
        )
        self.assertFalse(form.is_valid())
        form = AccountCreationForm(
            data={"email": "new@example.com", "password1": "123", "password2": "123"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_admin_views_for_superuser(self):
        user = User.objects.create_superuser("root@example.com", PASSWORD)
        self.client.force_login(user)
        for name, args in (
            ("admin:accounts_user_changelist", []),
            ("admin:accounts_user_add", []),
            ("admin:accounts_user_change", [user.pk]),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    self.client.get(reverse(name, args=args)).status_code, 200
                )

    def test_regular_user_cannot_access_admin(self):
        user = User.objects.create_user("regular@example.com", PASSWORD)
        self.client.force_login(user)
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertEqual(response.status_code, 302)
        user.is_staff = True
        user.save()
        self.assertEqual(
            self.client.get(reverse("admin:accounts_user_changelist")).status_code, 403
        )
