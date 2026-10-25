import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship

User = get_user_model()


class AcademicModelTests(TestCase):
    def setUp(self):
        self.student = Student.objects.create(first_name="Ada", last_name="Cianci")
        self.discipline = Discipline.objects.create(name="Jazz")
        self.guardian = User.objects.create_user("guardian@example.com", "Password-92!")
        self.staff = User.objects.create_user("staff@example.com", "Password-93!")

    def test_student_can_exist_without_account_guardian_or_enrollment(self):
        self.assertIsNone(self.student.user)
        self.assertEqual(self.student.guardians.count(), 0)
        self.assertEqual(self.student.enrollments.count(), 0)

    def test_discipline_name_is_case_insensitively_unique_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Discipline.objects.create(name="jAZz")

    def test_enrollment_can_be_repeated_after_ending_and_keeps_history(self):
        first = Enrollment.objects.create(
            student=self.student, discipline=self.discipline
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(student=self.student, discipline=self.discipline)

        first.ended_at = first.enrolled_at + timedelta(days=1)
        first.save(update_fields=("ended_at",))
        second = Enrollment.objects.create(
            student=self.student, discipline=self.discipline
        )

        self.assertEqual(self.student.enrollments.count(), 2)
        self.assertTrue(
            Enrollment.objects.filter(pk=second.pk, ended_at__isnull=True).exists()
        )

    def test_database_rejects_end_date_before_enrollment_date(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(
                student=self.student,
                discipline=self.discipline,
                enrolled_at=date(2026, 10, 25),
                ended_at=date(2026, 10, 24),
            )

    def test_guardian_revocation_preserves_history_and_allows_relinking(self):
        old = GuardianRelationship.objects.create(
            guardian=self.guardian,
            student=self.student,
            created_by=self.staff,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            GuardianRelationship.objects.create(
                guardian=self.guardian,
                student=self.student,
                created_by=self.staff,
            )

        old.revoked_at = old.created_at + timedelta(seconds=1)
        old.revoked_by = self.staff
        old.save(update_fields=("revoked_at", "revoked_by"))
        current = GuardianRelationship.objects.create(
            guardian=User.objects.create_user(
                "second-guardian@example.com", "Password-94!"
            ),
            student=self.student,
            created_by=self.staff,
        )
        relinked = GuardianRelationship.objects.create(
            guardian=self.guardian,
            student=self.student,
            created_by=self.staff,
        )

        self.assertEqual(GuardianRelationship.objects.count(), 3)
        self.assertEqual(
            GuardianRelationship.objects.filter(
                student=self.student, revoked_at__isnull=True
            ).count(),
            2,
        )
        self.assertEqual(self.student.guardians.count(), 2)
        self.assertCountEqual(
            self.student.guardians.values_list("pk", flat=True),
            [self.guardian.pk, current.guardian_id],
        )
        self.assertIsNone(current.revoked_at)
        self.assertIsNone(relinked.revoked_at)

    def test_inactive_discipline_rejects_a_new_active_enrollment(self):
        self.discipline.is_active = False
        self.discipline.save(update_fields=("is_active",))
        enrollment = Enrollment(
            student=self.student,
            discipline=self.discipline,
        )
        with self.assertRaises(ValidationError):
            enrollment.full_clean()


class ConcurrentEnrollmentTests(TransactionTestCase):
    def test_concurrent_active_enrollments_are_unique_in_postgresql(self):
        student = Student.objects.create(first_name="Ada", last_name="Cianci")
        discipline = Discipline.objects.create(name="Contemporáneo")
        barrier = threading.Barrier(2)

        def create_enrollment():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                with transaction.atomic():
                    Enrollment.objects.create(
                        student_id=student.pk,
                        discipline_id=discipline.pk,
                    )
                return "created"
            except IntegrityError:
                return "duplicate"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: create_enrollment(), range(2)))

        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Enrollment.objects.count(), 1)


class GuardianRelationshipConcurrencyTests(TransactionTestCase):
    def test_concurrent_active_guardian_relationships_are_unique(self):
        student = Student.objects.create(first_name="Luz", last_name="Cianci")
        guardian = User.objects.create_user("guardian@example.com", "Password-92!")
        staff = User.objects.create_user("staff@example.com", "Password-93!")
        barrier = threading.Barrier(2)

        def create_relationship():
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                with transaction.atomic():
                    GuardianRelationship.objects.create(
                        student_id=student.pk,
                        guardian_id=guardian.pk,
                        created_by_id=staff.pk,
                    )
                return "created"
            except IntegrityError:
                return "duplicate"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: create_relationship(), range(2)))

        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(GuardianRelationship.objects.count(), 1)
