from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship

User = get_user_model()
PASSWORD = "Safe-academic-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AcademicReadAPIViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user("user@example.com", PASSWORD)
        self.audit_user = User.objects.create_user("staff@example.com", PASSWORD)

    def login(self, user=None):
        self.client.force_login(user or self.user)

    def create_link(self, guardian, student):
        return GuardianRelationship.objects.create(
            guardian=guardian,
            student=student,
            created_by=self.audit_user,
        )

    def test_student_can_read_own_record_but_cannot_read_another_adults_enrollments(
        self,
    ):
        own = Student.objects.create(
            first_name="María", last_name="Cianci", user=self.user
        )
        another_user = User.objects.create_user("other@example.com", PASSWORD)
        another = Student.objects.create(
            first_name="Ana", last_name="Cianci", user=another_user
        )
        discipline = Discipline.objects.create(name="Bachata")
        Enrollment.objects.create(student=own, discipline=discipline)
        self.login()

        response = self.client.get(reverse("academic-my-students"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(
            response.json()["results"],
            [
                {
                    "id": own.pk,
                    "firstName": "María",
                    "lastName": "Cianci",
                    "accessType": "self",
                }
            ],
        )
        self.assertNotIn("dateOfBirth", response.json()["results"][0])
        response = self.client.get(
            reverse("academic-student-enrollments", args=(another.pk,))
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_tutor_access_requires_current_link_known_birth_date_and_age_under_18(self):
        guardian = self.user
        minor = Student.objects.create(
            first_name="Sofía", last_name="Cianci", date_of_birth=date(2014, 2, 1)
        )
        adult = Student.objects.create(
            first_name="Ana", last_name="Cianci", date_of_birth=date(2000, 2, 1)
        )
        unknown_age = Student.objects.create(first_name="Eva", last_name="Cianci")
        unrelated_minor = Student.objects.create(
            first_name="Luz", last_name="Cianci", date_of_birth=date(2015, 3, 1)
        )
        self.create_link(guardian, minor)
        self.create_link(guardian, adult)
        self.create_link(guardian, unknown_age)
        self.login()

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 25)
        ):
            response = self.client.get(reverse("academic-my-students"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.json()["results"]], [minor.pk]
        )
        self.assertEqual(response.json()["results"][0]["accessType"], "guardian")
        for unauthorized_student in (adult, unknown_age, unrelated_minor):
            response = self.client.get(
                reverse(
                    "academic-student-enrollments",
                    args=(unauthorized_student.pk,),
                )
            )
            self.assertEqual(response.status_code, 404)

    def test_access_ends_on_eighteenth_birthday_including_february_29_birthdays(self):
        guardian = self.user
        birthday_today = Student.objects.create(
            first_name="Elena", last_name="Cumple", date_of_birth=date(2008, 10, 25)
        )
        leap_day_student = Student.objects.create(
            first_name="Lucía", last_name="Bisiesta", date_of_birth=date(2008, 2, 29)
        )
        self.create_link(guardian, birthday_today)
        self.create_link(guardian, leap_day_student)
        self.login()

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 24)
        ):
            before_birthday = self.client.get(reverse("academic-my-students"))
        self.assertEqual(
            {item["id"] for item in before_birthday.json()["results"]},
            {birthday_today.pk},
        )

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 25)
        ):
            on_birthday = self.client.get(reverse("academic-my-students"))
        self.assertEqual(on_birthday.json()["results"], [])

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 2, 28)
        ):
            before_leap_birthday = self.client.get(reverse("academic-my-students"))
        self.assertEqual(
            {item["id"] for item in before_leap_birthday.json()["results"]},
            {birthday_today.pk, leap_day_student.pk},
        )

        with patch("academy.queries.timezone.localdate", return_value=date(2026, 3, 1)):
            on_leap_birthday = self.client.get(reverse("academic-my-students"))
        self.assertEqual(
            [item["id"] for item in on_leap_birthday.json()["results"]],
            [birthday_today.pk],
        )

    def test_revocation_blocks_next_request_without_ending_the_session(self):
        minor = Student.objects.create(
            first_name="Sofía", last_name="Cianci", date_of_birth=date(2014, 2, 1)
        )
        relationship = self.create_link(self.user, minor)
        self.login()

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 25)
        ):
            self.assertEqual(
                self.client.get(reverse("academic-my-students")).status_code, 200
            )
            relationship.revoked_at = timezone.now()
            relationship.revoked_by = self.audit_user
            relationship.save(update_fields=("revoked_at", "revoked_by"))

            response = self.client.get(
                reverse("academic-student-enrollments", args=(minor.pk,))
            )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(self.client.session.session_key)
        self.assertIsNotNone(relationship.revoked_at)

    def test_multiple_guardians_and_combined_student_tutor_account(self):
        own_student = Student.objects.create(
            first_name="María", last_name="Cianci", user=self.user
        )
        minor = Student.objects.create(
            first_name="Sofía", last_name="Cianci", date_of_birth=date(2014, 2, 1)
        )
        second_guardian = User.objects.create_user("second@example.com", PASSWORD)
        self.create_link(self.user, minor)
        self.create_link(second_guardian, minor)
        bachata = Discipline.objects.create(name="Bachata")
        jazz = Discipline.objects.create(name="Jazz")
        Enrollment.objects.create(student=own_student, discipline=bachata)
        Enrollment.objects.create(student=minor, discipline=jazz)
        self.login()

        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 25)
        ):
            students = self.client.get(reverse("academic-my-students")).json()[
                "results"
            ]
            own_enrollments = self.client.get(
                reverse("academic-student-enrollments", args=(own_student.pk,))
            ).json()["results"]
            minor_enrollments = self.client.get(
                reverse("academic-student-enrollments", args=(minor.pk,))
            ).json()["results"]

        self.assertEqual(
            {item["accessType"] for item in students}, {"self", "guardian"}
        )
        self.assertEqual(own_enrollments[0]["discipline"]["name"], "Bachata")
        self.assertEqual(minor_enrollments[0]["discipline"]["name"], "Jazz")

        self.client.force_login(second_guardian)
        with patch(
            "academy.queries.timezone.localdate", return_value=date(2026, 10, 25)
        ):
            other_guardian_students = self.client.get(
                reverse("academic-my-students")
            ).json()["results"]
        self.assertEqual([item["id"] for item in other_guardian_students], [minor.pk])

    def test_enrollment_status_filter_and_history(self):
        student = Student.objects.create(
            first_name="María", last_name="Cianci", user=self.user
        )
        discipline = Discipline.objects.create(name="Bachata")
        old = Enrollment.objects.create(
            student=student,
            discipline=discipline,
            enrolled_at=date(2024, 1, 1),
            ended_at=date(2024, 12, 1),
        )
        current = Enrollment.objects.create(
            student=student, discipline=discipline, enrolled_at=date(2026, 1, 1)
        )
        self.login()
        url = reverse("academic-student-enrollments", args=(student.pk,))

        active = self.client.get(url)
        history = self.client.get(url, {"status": "history"})
        all_records = self.client.get(url, {"status": "all"})
        invalid = self.client.get(url, {"status": "pending"})

        self.assertEqual([row["id"] for row in active.json()["results"]], [current.pk])
        self.assertEqual([row["id"] for row in history.json()["results"]], [old.pk])
        self.assertEqual(
            [row["id"] for row in all_records.json()["results"]],
            [current.pk, old.pk],
        )
        self.assertEqual(all_records.json()["results"][1]["status"], "history")
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid["Cache-Control"], "no-store")

    def test_anonymous_and_user_without_academic_records(self):
        response = self.client.get(reverse("academic-my-students"))
        self.assertIn(response.status_code, (401, 403))

        self.login()
        response = self.client.get(reverse("academic-my-students"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

        self.user.is_staff = True
        self.user.save(update_fields=("is_staff",))
        response = self.client.get(reverse("academic-my-students"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
