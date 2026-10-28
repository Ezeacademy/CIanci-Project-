from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from academy.models import Discipline


class PublicDisciplineListTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_anonymous_landing_receives_only_active_disciplines_in_order(self):
        Discipline.objects.create(name="Jazz")
        Discipline.objects.create(name="Clásico")
        Discipline.objects.create(name="Contemporáneo", is_active=False)

        response = self.client.get(reverse("public-academic-disciplines"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "id": Discipline.objects.get(name="Clásico").pk,
                    "name": "Clásico",
                },
                {"id": Discipline.objects.get(name="Jazz").pk, "name": "Jazz"},
            ],
        )

