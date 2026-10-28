from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
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

    def test_function_creation_accepts_local_date_time_from_argentine_form(self):
        owner = User.objects.create_superuser(
            "function-time-owner@example.com", "Ticket-pass-95!"
        )
        venue = Venue.objects.create(name="Teatro Fecha Local")
        map_version = create_map_version(venue.pk, owner, sample_sections())
        show = Show.objects.create(title="Función con hora local")
        platea = map_version.sections.get(name="Platea")
        self.client.force_login(owner)

        response = self.client.post(
            f"/api/v1/admin/ticketing/shows/{show.pk}/functions",
            {
                "mapVersionId": map_version.pk,
                "startsAt": "2027-02-01T19:30:00",
                "sectionPrices": [{"sectionId": platea.pk, "amount": "12500.00"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        created_function = ShowFunction.objects.get(pk=response.data["id"])
        self.assertEqual(
            timezone.localtime(created_function.starts_at).strftime("%Y-%m-%d %H:%M"),
            "2027-02-01 19:30",
        )

    def test_function_update_changes_time_and_prices_with_audit(self):
        owner = User.objects.create_superuser(
            "function-update-owner@example.com", "Ticket-pass-96!"
        )
        venue = Venue.objects.create(name="Teatro Función Editable")
        map_version = create_map_version(venue.pk, owner, sample_sections())
        show = Show.objects.create(title="Gala editable")
        platea = map_version.sections.get(name="Platea")
        function = create_show_function(
            show=show,
            map_version=map_version,
            starts_at=timezone.now() + timedelta(days=20),
            section_prices=[{"section_id": platea.pk, "amount": "12000.00"}],
            actor=owner,
        )
        self.client.force_login(owner)

        response = self.client.patch(
            f"/api/v1/admin/ticketing/functions/{function.pk}",
            {
                "startsAt": "2027-04-18T20:15:00",
                "sectionPrices": [{"sectionId": platea.pk, "amount": "13500.00"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        function.refresh_from_db()
        self.assertEqual(
            timezone.localtime(function.starts_at).strftime("%Y-%m-%d %H:%M"),
            "2027-04-18 20:15",
        )
        self.assertEqual(
            function.section_prices.get(section=platea).amount, Decimal("13500.00")
        )
        self.assertEqual(function.updated_by, owner)
        self.assertIsNotNone(function.updated_at)

    def test_function_update_rejects_duplicate_time_and_foreign_sector_atomically(self):
        owner = User.objects.create_superuser(
            "function-conflict-owner@example.com", "Ticket-pass-97!"
        )
        venue = Venue.objects.create(name="Teatro Función Conflicto")
        first_map = create_map_version(venue.pk, owner, sample_sections())
        second_map = create_map_version_from(first_map.pk, owner)
        show = Show.objects.create(title="Gala sin duplicados")
        first_platea = first_map.sections.get(name="Platea")
        second_platea = second_map.sections.get(name="Platea")
        first_function = create_show_function(
            show=show,
            map_version=first_map,
            starts_at=timezone.now() + timedelta(days=30),
            section_prices=[{"section_id": first_platea.pk, "amount": "10000.00"}],
        )
        second_function = create_show_function(
            show=show,
            map_version=second_map,
            starts_at=timezone.now() + timedelta(days=31),
            section_prices=[],
        )
        self.client.force_login(owner)

        duplicate_time = self.client.patch(
            f"/api/v1/admin/ticketing/functions/{first_function.pk}",
            {"startsAt": second_function.starts_at.isoformat()},
            format="json",
        )
        self.assertEqual(duplicate_time.status_code, 400)

        invalid_sector = self.client.patch(
            f"/api/v1/admin/ticketing/functions/{first_function.pk}",
            {
                "startsAt": "2027-05-01T18:00:00",
                "sectionPrices": [
                    {"sectionId": second_platea.pk, "amount": "15000.00"}
                ],
            },
            format="json",
        )
        self.assertEqual(invalid_sector.status_code, 400)
        first_function.refresh_from_db()
        self.assertNotEqual(first_function.starts_at, second_function.starts_at)
        self.assertEqual(
            first_function.section_prices.get(section=first_platea).amount,
            Decimal("10000.00"),
        )

    def test_function_update_requires_management_permission(self):
        venue = Venue.objects.create(name="Teatro Permiso Función")
        map_version = create_map_version(venue.pk, self.staff, sample_sections())
        show = Show.objects.create(title="Gala protegida")
        function = ShowFunction.objects.create(
            show=show,
            map_version=map_version,
            starts_at=timezone.now() + timedelta(days=40),
        )
        self.client.force_login(self.staff)
        url = f"/api/v1/admin/ticketing/functions/{function.pk}"

        self.assertEqual(
            self.client.patch(
                url, {"startsAt": "2027-06-01T18:00:00"}, format="json"
            ).status_code,
            403,
        )
        self.grant(self.staff, "view_show")
        self.assertEqual(
            self.client.patch(
                url, {"startsAt": "2027-06-01T18:00:00"}, format="json"
            ).status_code,
            403,
        )
        self.grant(self.staff, "manage_ticketing")
        self.assertEqual(
            self.client.patch(
                url, {"startsAt": "2027-06-01T18:00:00"}, format="json"
            ).status_code,
            200,
        )

    def test_venue_can_retain_its_current_name_when_editing(self):
        owner = User.objects.create_superuser(
            "venue-update-owner@example.com", "Ticket-pass-98!"
        )
        venue = Venue.objects.create(name="Teatro Mismo Nombre")
        self.client.force_login(owner)

        response = self.client.patch(
            f"/api/v1/admin/ticketing/venues/{venue.pk}",
            {"name": venue.name, "location": "Nueva ubicación"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        venue.refresh_from_db()
        self.assertEqual(venue.location, "Nueva ubicación")

    def test_unfrozen_map_edit_is_audited_and_frozen_map_remains_protected(self):
        owner = User.objects.create_superuser(
            "map-update-owner@example.com", "Ticket-pass-99!"
        )
        venue = Venue.objects.create(name="Teatro Mapa Auditado")
        map_version = create_map_version(venue.pk, owner, sample_sections())
        show = Show.objects.create(title="Gala que congela mapa")
        ShowFunction.objects.create(
            show=show,
            map_version=map_version,
            starts_at=timezone.now() + timedelta(days=50),
        )
        editable_map = create_map_version_from(map_version.pk, owner)
        self.client.force_login(owner)
        frozen_url = f"/api/v1/admin/ticketing/maps/{map_version.pk}"

        frozen_response = self.client.put(
            frozen_url, {"sections": sample_sections()}, format="json"
        )

        self.assertEqual(frozen_response.status_code, 400)
        self.assertIn("nueva versión", str(frozen_response.data).lower())
        editable_url = f"/api/v1/admin/ticketing/maps/{editable_map.pk}"
        editable_response = self.client.put(
            editable_url, {"sections": sample_sections()}, format="json"
        )

        self.assertEqual(editable_response.status_code, 200)
        editable_map.refresh_from_db()
        self.assertEqual(editable_map.updated_by, owner)


class PublicTicketingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            "public-ticket-admin@example.com", "Ticket-pass-94!", is_staff=True
        )
        self.venue = Venue.objects.create(
            name="Teatro Público", location="Calle 123, Buenos Aires"
        )
        self.map_version = create_map_version(
            self.venue.pk, self.admin, sample_sections()
        )
        self.published_show = Show.objects.create(
            title="Gala de danza",
            description="Una noche de movimiento.",
            image_url="https://images.example.test/gala.jpg",
            status=Show.Status.PUBLISHED,
        )
        self.function = create_show_function(
            show=self.published_show,
            map_version=self.map_version,
            starts_at=timezone.now() + timedelta(days=30),
            section_prices=[
                {
                    "section_id": self.map_version.sections.get(name="Platea").pk,
                    "amount": Decimal("12500.00"),
                },
                {
                    "section_id": self.map_version.sections.get(name="Pullman").pk,
                    "amount": Decimal("9000.00"),
                },
            ],
        )

    def test_public_catalog_requires_no_login_and_hides_unpublished_shows(self):
        Show.objects.create(title="Borrador", status=Show.Status.DRAFT)
        Show.objects.create(title="Archivado", status=Show.Status.ARCHIVED)

        response = self.client.get("/api/v1/ticketing/shows")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([show["title"] for show in response.data], ["Gala de danza"])
        self.assertEqual(response.data[0]["functions"][0]["venue"], "Teatro Público")
        self.assertNotIn("status", response.data[0])
        self.assertNotIn("createdBy", response.data[0])

    def test_public_detail_exposes_real_layout_prices_and_operational_state(self):
        response = self.client.get(f"/api/v1/ticketing/shows/{self.published_show.pk}")

        self.assertEqual(response.status_code, 200)
        function_summary = response.data["functions"][0]
        self.assertNotIn("sections", function_summary)
        function = self.client.get(
            f"/api/v1/ticketing/shows/{self.published_show.pk}/functions/"
            f"{self.function.pk}/seat-map"
        ).data
        platea = next(
            section for section in function["sections"] if section["name"] == "Platea"
        )
        self.assertEqual(platea["price"], "12500.00")
        self.assertEqual(platea["rows"][0]["gaps"][0]["kind"], "aisle")
        self.assertEqual(platea["rows"][0]["seats"][1]["isOperational"], False)
        self.assertEqual(function["capacity"], 5)
        self.assertNotIn("mapVersionId", function)
        self.assertNotIn("createdBy", function)

    def test_public_detail_does_not_reveal_draft_or_archived_show(self):
        hidden_show = Show.objects.create(title="Ensayo", status=Show.Status.DRAFT)

        response = self.client.get(f"/api/v1/ticketing/shows/{hidden_show.pk}")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            self.client.get(
                f"/api/v1/ticketing/shows/{hidden_show.pk}/functions/"
                f"{self.function.pk}/seat-map"
            ).status_code,
            404,
        )

    def test_catalog_does_not_include_past_functions(self):
        ShowFunction.objects.create(
            show=self.published_show,
            map_version=self.map_version,
            starts_at=timezone.now() - timedelta(days=1),
        )

        response = self.client.get("/api/v1/ticketing/shows")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data[0]["functions"]), 1)
        self.assertEqual(response.data[0]["functions"][0]["id"], self.function.pk)

    def test_public_detail_distinguishes_past_functions_from_no_functions(self):
        past_show = Show.objects.create(
            title="Funciones realizadas", status=Show.Status.PUBLISHED
        )
        ShowFunction.objects.create(
            show=past_show,
            map_version=self.map_version,
            starts_at=timezone.now() - timedelta(days=1),
        )
        show_without_functions = Show.objects.create(
            title="Sin funciones", status=Show.Status.PUBLISHED
        )

        past_response = self.client.get(f"/api/v1/ticketing/shows/{past_show.pk}")
        empty_response = self.client.get(
            f"/api/v1/ticketing/shows/{show_without_functions.pk}"
        )

        self.assertEqual(past_response.status_code, 200)
        self.assertEqual(past_response.data["functions"], [])
        self.assertTrue(past_response.data["hasPastFunctions"])
        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.data["functions"], [])
        self.assertFalse(empty_response.data["hasPastFunctions"])
