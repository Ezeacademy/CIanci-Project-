from datetime import datetime
from datetime import timezone as datetime_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import (
    FunctionSectionPrice,
    SeatRow,
    Show,
    ShowFunction,
    Venue,
)
from .services import (
    create_map_version,
    create_map_version_from,
    create_show_function,
)

User = get_user_model()


def sample_sections():
    return [
        {
            "name": "Platea",
            "rows": [
                {
                    "label": "A",
                    "seats": [
                        {"number": "1", "position": 1},
                        {"number": "2", "position": 2, "isOperational": False},
                    ],
                    "gaps": [{"position": 3, "kind": "aisle"}],
                },
                {
                    "label": "B",
                    "seats": [
                        {"number": str(number), "position": number}
                        for number in range(1, 4)
                    ],
                },
            ],
        },
        {
            "name": "Pullman",
            "rows": [{"label": "1", "seats": [{"number": "A", "position": 1}]}],
        },
    ]


class TicketingModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "ticket-admin@example.com", "Ticket-pass-92!", is_staff=True
        )
        self.venue = Venue.objects.create(name="Teatro Cianci", location="Buenos Aires")

    def test_map_capacity_counts_only_operational_seats_in_irregular_rows(self):
        version = create_map_version(self.venue.pk, self.user, sample_sections())
        self.assertEqual(version.capacity, 5)
        self.assertEqual(version.sections.count(), 2)
        self.assertEqual(version.sections.get(name="Platea").rows.count(), 2)

    def test_invalid_map_creation_rolls_back_all_structure(self):
        sections = [
            {
                "name": "Platea",
                "rows": [
                    {
                        "label": "A",
                        "seats": [
                            {"number": "1", "position": 1},
                            {"number": "1", "position": 2},
                        ],
                    }
                ],
            }
        ]
        with self.assertRaises(IntegrityError):
            create_map_version(self.venue.pk, self.user, sections)
        self.assertEqual(self.venue.map_versions.count(), 0)

    def test_map_version_freezes_after_function_association(self):
        version = create_map_version(self.venue.pk, self.user, sample_sections())
        show = Show.objects.create(title="Muestra anual")
        function = create_show_function(
            show=show,
            map_version=version,
            starts_at=datetime(2027, 2, 1, 20, 0, tzinfo=datetime_timezone.utc),
            section_prices=[],
        )
        self.assertEqual(function.capacity, 5)
        self.assertTrue(version.is_frozen)
        with self.assertRaises(ValidationError):
            SeatRow.objects.create(section=version.sections.first(), label="C")

    def test_price_is_unique_for_function_and_section_and_not_shared_between_functions(
        self,
    ):
        version = create_map_version(self.venue.pk, self.user, sample_sections())
        show = Show.objects.create(title="Función doble")
        section = version.sections.first()
        first = create_show_function(
            show=show,
            map_version=version,
            starts_at=datetime(2027, 2, 1, 19, 0, tzinfo=datetime_timezone.utc),
            section_prices=[],
        )
        second = ShowFunction.objects.create(
            show=show,
            map_version=version,
            starts_at=datetime(2027, 2, 1, 21, 0, tzinfo=datetime_timezone.utc),
        )
        FunctionSectionPrice.objects.create(
            function=first, section=section, amount=Decimal("12000.00")
        )
        FunctionSectionPrice.objects.create(
            function=second, section=section, amount=Decimal("15000.00")
        )
        self.assertEqual(first.section_prices.get().amount, Decimal("12000.00"))
        self.assertEqual(second.section_prices.get().amount, Decimal("15000.00"))
        with self.assertRaises(IntegrityError), transaction.atomic():
            FunctionSectionPrice.objects.bulk_create(
                [
                    FunctionSectionPrice(
                        function=first, section=section, amount=Decimal("100.00")
                    )
                ]
            )

    def test_show_rejects_non_https_image_url(self):
        show = Show(title="Gala", image_url="http://example.test/gala.jpg")
        with self.assertRaises(ValidationError):
            show.save()

    def test_copying_map_creates_a_new_editable_version_without_changing_history(self):
        original = create_map_version(self.venue.pk, self.user, sample_sections())
        show = Show.objects.create(title="Noche de danza")
        create_show_function(
            show=show,
            map_version=original,
            starts_at=datetime(2027, 4, 1, 20, 0, tzinfo=datetime_timezone.utc),
            section_prices=[],
        )

        copy = create_map_version_from(original.pk, self.user)

        self.assertEqual(copy.version_number, 2)
        self.assertFalse(copy.is_frozen)
        self.assertTrue(original.is_frozen)
        self.assertEqual(copy.capacity, original.capacity)
        self.assertNotEqual(
            copy.sections.first().rows.first().seats.first().pk,
            original.sections.first().rows.first().seats.first().pk,
        )


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class TicketingPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            "staff-ticket@example.com", "Ticket-pass-92!", is_staff=True
        )
        self.url = "/api/v1/admin/ticketing/venues"

    def grant(self, user, codename):
        permission = Permission.objects.get(
            content_type__app_label="tickets", codename=codename
        )
        user.user_permissions.add(permission)

    def test_endpoint_requires_authentication_and_management_permission(self):
        self.assertIn(self.client.get(self.url).status_code, (401, 403))
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.post(self.url, {"name": "Teatro"}, format="json").status_code,
            403,
        )
        self.grant(self.staff, "manage_ticketing")
        self.assertEqual(
            self.client.post(self.url, {"name": "Teatro"}, format="json").status_code,
            201,
        )

    def test_view_permission_does_not_allow_creation(self):
        self.client.force_login(self.staff)
        self.grant(self.staff, "view_show")
        self.assertEqual(self.client.get(self.url).status_code, 200)
        self.assertEqual(
            self.client.post(self.url, {"name": "Teatro"}, format="json").status_code,
            403,
        )

    def test_superuser_can_create_and_edit_show_without_explicit_permissions(self):
        owner = User.objects.create_superuser(
            "owner-ticket@example.com", "Ticket-pass-93!"
        )
        self.client.force_login(owner)
        created = self.client.post(
            "/api/v1/admin/ticketing/shows",
            {"title": "Gala", "imageUrl": "https://example.test/gala.jpg"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        changed = self.client.patch(
            f"/api/v1/admin/ticketing/shows/{created.data['id']}",
            {"status": "published"},
            format="json",
        )
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.data["status"], "published")
