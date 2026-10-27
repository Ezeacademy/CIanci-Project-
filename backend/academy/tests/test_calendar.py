from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from academy.models import ClassSchedule, Discipline, Enrollment, Student, Teacher
from academy.schedules import get_next_class_occurrence
from accounts.models import GuardianRelationship


class ClassScheduleModelTests(TestCase):
    def setUp(self):
        self.discipline = Discipline.objects.create(name="Jazz Inicial")
        self.teacher = Teacher.objects.create(first_name="Loli", last_name="Pérez")

    def create_schedule(self, **overrides):
        values = {
            "discipline": self.discipline,
            "teacher": self.teacher,
            "weekday": 0,
            "start_time": time(18, 0),
            "end_time": time(19, 30),
        }
        values.update(overrides)
        return ClassSchedule.objects.create(**values)

    def test_teacher_and_multiple_weekly_schedules_can_be_created(self):
        monday = self.create_schedule()
        saturday = self.create_schedule(
            weekday=5, start_time=time(9), end_time=time(10, 30)
        )

        self.assertEqual(Teacher.objects.count(), 1)
        self.assertEqual(
            list(self.discipline.class_schedules.all()), [monday, saturday]
        )
        self.assertFalse(hasattr(self.teacher, "user"))

    def test_schedule_requires_end_time_after_start(self):
        with self.assertRaises(ValidationError):
            self.create_schedule(start_time=time(19), end_time=time(19))
        with self.assertRaises(ValidationError):
            self.create_schedule(start_time=time(20), end_time=time(19))

    def test_active_exact_slot_is_unique_but_inactive_history_can_remain(self):
        original = self.create_schedule()
        with self.assertRaises(ValidationError):
            self.create_schedule()

        original.is_active = False
        original.save()
        replacement = self.create_schedule()
        self.assertFalse(original.is_active)
        self.assertTrue(replacement.is_active)

    def test_database_rejects_duplicate_active_slots_and_invalid_weekdays(self):
        self.create_schedule()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ClassSchedule.objects.bulk_create(
                [
                    ClassSchedule(
                        discipline=self.discipline,
                        teacher=self.teacher,
                        weekday=0,
                        start_time=time(18),
                        end_time=time(19, 30),
                    )
                ]
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            ClassSchedule.objects.bulk_create(
                [
                    ClassSchedule(
                        discipline=self.discipline,
                        teacher=self.teacher,
                        weekday=7,
                        start_time=time(20),
                        end_time=time(21),
                    )
                ]
            )

    def test_deactivating_teacher_preserves_schedule_history(self):
        schedule = self.create_schedule()
        self.teacher.is_active = False
        self.teacher.save(update_fields=("is_active",))

        schedule.refresh_from_db()
        self.assertTrue(schedule.is_active)
        self.assertEqual(schedule.teacher, self.teacher)


class NextClassOccurrenceTests(TestCase):
    def setUp(self):
        self.teacher = Teacher.objects.create(first_name="Loli", last_name="Pérez")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.schedule = ClassSchedule.objects.create(
            discipline=self.discipline,
            teacher=self.teacher,
            weekday=0,
            start_time=time(18),
            end_time=time(19, 30),
        )
        self.buenos_aires = ZoneInfo("America/Argentina/Buenos_Aires")

    def test_next_occurrence_before_class_today(self):
        reference = datetime(2026, 6, 1, 17, 59, tzinfo=self.buenos_aires)

        result = get_next_class_occurrence(self.schedule, reference=reference)

        self.assertEqual(result, datetime(2026, 6, 1, 18, tzinfo=self.buenos_aires))

    def test_class_start_is_exclusive_and_rolls_to_next_week(self):
        reference = datetime(2026, 6, 1, 18, tzinfo=self.buenos_aires)

        result = get_next_class_occurrence(self.schedule, reference=reference)

        self.assertEqual(result, datetime(2026, 6, 8, 18, tzinfo=self.buenos_aires))

    def test_future_enrollment_never_receives_an_earlier_occurrence(self):
        reference = datetime(2026, 6, 1, 17, tzinfo=self.buenos_aires)

        result = get_next_class_occurrence(
            self.schedule,
            reference=reference,
            not_before=date(2026, 6, 9),
        )

        self.assertEqual(result, datetime(2026, 6, 15, 18, tzinfo=self.buenos_aires))


class PrivateClassCalendarAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "student@example.com", "Safe-password-92!"
        )
        self.guardian = get_user_model().objects.create_user(
            "guardian@example.com", "Safe-password-92!"
        )
        self.staff = get_user_model().objects.create_user(
            "admin@example.com", "Safe-password-92!"
        )
        self.student = Student.objects.create(
            first_name="Ana", last_name="Cianci", user=self.user
        )
        self.minor = Student.objects.create(
            first_name="Sol",
            last_name="Cianci",
            date_of_birth=date(2015, 4, 1),
        )
        self.other = Student.objects.create(first_name="Eva", last_name="Ajena")
        GuardianRelationship.objects.create(
            guardian=self.guardian, student=self.minor, created_by=self.staff
        )
        self.discipline = Discipline.objects.create(name="Jazz Inicial")
        self.teacher = Teacher.objects.create(first_name="Loli", last_name="Pérez")
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            discipline=self.discipline,
            enrolled_at=date(2026, 1, 1),
        )
        self.schedule = ClassSchedule.objects.create(
            discipline=self.discipline,
            teacher=self.teacher,
            weekday=5,
            start_time=time(9),
            end_time=time(10, 30),
        )
        self.client = APIClient()

    def test_student_sees_active_enrollments_and_sorted_schedules_privately(self):
        Enrollment.objects.create(
            student=self.student,
            discipline=Discipline.objects.create(name="Jazz Intermedio"),
            enrolled_at=date(2026, 1, 1),
            ended_at=date(2026, 5, 1),
        )
        second_discipline = Discipline.objects.create(name="Contemporáneo")
        Enrollment.objects.create(
            student=self.student,
            discipline=second_discipline,
            enrolled_at=date(2026, 1, 1),
        )
        ClassSchedule.objects.create(
            discipline=second_discipline,
            teacher=self.teacher,
            weekday=0,
            start_time=time(18),
            end_time=time(19),
        )
        inactive_discipline = Discipline.objects.create(
            name="Clásico archivado", is_active=False
        )
        Enrollment.objects.create(
            student=self.student,
            discipline=inactive_discipline,
            enrolled_at=date(2026, 1, 1),
        )
        inactive_schedule = ClassSchedule.objects.create(
            discipline=inactive_discipline,
            teacher=self.teacher,
            weekday=1,
            start_time=time(16),
            end_time=time(17),
            is_active=False,
        )
        del inactive_schedule

        self.client.force_login(self.user)
        response = self.client.get(reverse("academic-my-calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        data = response.json()["results"]
        self.assertEqual(
            [item["discipline"]["name"] for item in data],
            [
                "Clásico archivado",
                "Contemporáneo",
                "Jazz Inicial",
            ],
        )
        self.assertEqual(data[0]["schedules"], [])
        self.assertEqual(
            [item["startTime"] for item in data[1]["schedules"]], ["18:00"]
        )
        self.assertEqual(data[2]["schedules"][0]["weekdayName"], "Sábado")
        self.assertTrue(data[2]["schedules"][0]["nextClass"].endswith("-03:00"))
        self.assertFalse(any(item["student"]["id"] == self.other.pk for item in data))

    def test_tutor_sees_only_currently_linked_students(self):
        other_discipline = Discipline.objects.create(name="Ballet")
        Enrollment.objects.create(
            student=self.minor,
            discipline=other_discipline,
            enrolled_at=date(2026, 1, 1),
        )
        self.client.force_login(self.guardian)

        response = self.client.get(reverse("academic-my-calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {item["student"]["id"] for item in response.json()["results"]},
            {self.minor.pk},
        )

    def test_anonymous_and_unrelated_user_cannot_see_calendar(self):
        self.assertEqual(
            self.client.get(reverse("academic-my-calendar")).status_code, 403
        )
        unrelated = get_user_model().objects.create_user(
            "unrelated@example.com", "Safe-password-92!"
        )
        self.client.force_login(unrelated)

        response = self.client.get(reverse("academic-my-calendar"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])

    def test_ended_enrollments_and_inactive_teachers_have_no_future_schedule(self):
        self.enrollment.ended_at = date(2026, 10, 1)
        self.enrollment.save(update_fields=("ended_at",))
        self.teacher.is_active = False
        self.teacher.save(update_fields=("is_active",))
        self.client.force_login(self.user)

        response = self.client.get(reverse("academic-my-calendar"))

        self.assertEqual(response.json()["results"], [])


class ClassScheduleAdminTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            "admin@example.com", "Safe-password-92!"
        )
        self.client = APIClient()
        self.client.force_login(self.admin_user)
        self.discipline = Discipline.objects.create(name="Jazz")
        self.teacher = Teacher.objects.create(first_name="Loli", last_name="Pérez")

    def test_discipline_and_teacher_admin_pages_show_schedule_management_and_history(
        self,
    ):
        ClassSchedule.objects.create(
            discipline=self.discipline,
            teacher=self.teacher,
            weekday=0,
            start_time=time(18),
            end_time=time(19),
        )

        discipline_response = self.client.get(
            reverse("admin:academy_discipline_change", args=(self.discipline.pk,))
        )
        teacher_response = self.client.get(
            reverse("admin:academy_teacher_change", args=(self.teacher.pk,))
        )

        self.assertContains(discipline_response, "Horarios semanales")
        self.assertContains(teacher_response, "Jazz")
        self.assertContains(teacher_response, "Lunes")
