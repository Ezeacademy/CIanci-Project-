from datetime import date
from unittest.mock import Mock, patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academy.models import Discipline, Enrollment, Student
from accounts.models import GuardianRelationship

User = get_user_model()
PASSWORD = "Safe-admin-passphrase-92!"


@override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
class AcademicAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("admin@example.com", PASSWORD)
        self.client = Client()
        self.client.force_login(self.admin_user)

    def test_standard_model_permissions_restrict_admin_to_authorized_staff(self):
        staff = User.objects.create_user("staff@example.com", PASSWORD, is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("admin:academy_student_changelist"))
        self.assertEqual(response.status_code, 403)

        permission = Permission.objects.get(
            content_type__app_label="academy", codename="view_student"
        )
        staff.user_permissions.add(permission)
        response = self.client.get(reverse("admin:academy_student_changelist"))
        self.assertEqual(response.status_code, 200)

        relationship_add = reverse("admin:accounts_guardianrelationship_add")
        self.assertEqual(self.client.get(relationship_add).status_code, 403)
        add_permission = Permission.objects.get(
            content_type__app_label="accounts",
            codename="add_guardianrelationship",
        )
        staff.user_permissions.add(add_permission)
        self.assertEqual(self.client.get(relationship_add).status_code, 200)
        guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        student = Student.objects.create(first_name="Ada", last_name="Cianci")
        response = self.client.post(
            relationship_add,
            {"guardian": guardian.pk, "students": [student.pk]},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            GuardianRelationship.objects.get(
                guardian=guardian, student=student
            ).created_by,
            staff,
        )

    @patch("academy.services.generate_monthly_charges")
    def test_admin_enrollment_creation_uses_shared_initial_charge_service(
        self, generate_charges
    ):
        today = timezone.localdate()
        generate_charges.return_value = Mock(created=1, missing_prices=())
        student = Student.objects.create(first_name="Ada", last_name="Cianci")
        discipline = Discipline.objects.create(name="Jazz")

        response = self.client.post(
            reverse("admin:academy_enrollment_add"),
            {
                "student": student.pk,
                "discipline": discipline.pk,
                "enrolled_at": today.isoformat(),
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        enrollment = Enrollment.objects.get(student=student, discipline=discipline)
        generate_charges.assert_called_once_with(
            billing_period=today.replace(day=1),
            enrollment_ids=(enrollment.pk,),
        )

    def test_guardian_creation_and_revocation_take_actor_from_admin_session(self):
        guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        forged_actor = User.objects.create_user("other@example.com", PASSWORD)
        student = Student.objects.create(first_name="Ada", last_name="Cianci")

        response = self.client.post(
            reverse("admin:accounts_guardianrelationship_add"),
            {
                "guardian": guardian.pk,
                "students": [student.pk],
                "created_by": forged_actor.pk,
                "revoked_by": forged_actor.pk,
            },
        )
        self.assertEqual(response.status_code, 302)
        relationship = GuardianRelationship.objects.get(
            guardian=guardian, student=student
        )
        self.assertEqual(relationship.created_by, self.admin_user)
        self.assertIsNone(relationship.revoked_by)

        self.client.post(
            reverse("admin:accounts_guardianrelationship_changelist"),
            {
                "action": "revoke_relationships",
                "_selected_action": [relationship.pk],
                "index": 0,
                "revoked_by": forged_actor.pk,
            },
        )
        relationship.refresh_from_db()
        self.assertIsNotNone(relationship.revoked_at)
        self.assertEqual(relationship.revoked_by, self.admin_user)
        self.assertEqual(GuardianRelationship.objects.count(), 1)

    def test_duplicate_single_link_shows_form_error_without_creating_a_row(self):
        guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        student = Student.objects.create(first_name="Ada", last_name="Cianci")
        GuardianRelationship.objects.create(
            guardian=guardian, student=student, created_by=self.admin_user
        )

        response = self.client.post(
            reverse("admin:accounts_guardianrelationship_add"),
            {"guardian": guardian.pk, "students": [student.pk]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este tutor ya está vinculado con este alumno.")
        self.assertEqual(GuardianRelationship.objects.count(), 1)

    def test_guardian_changelist_shows_spanish_status_and_filters_history(self):
        guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        current_student = Student.objects.create(first_name="Ana", last_name="Cianci")
        former_student = Student.objects.create(first_name="Bea", last_name="Cianci")
        current = GuardianRelationship.objects.create(
            guardian=guardian, student=current_student, created_by=self.admin_user
        )
        former = GuardianRelationship.objects.create(
            guardian=guardian, student=former_student, created_by=self.admin_user
        )
        former.revoked_at = former.created_at
        former.revoked_by = self.admin_user
        former.save(update_fields=("revoked_at", "revoked_by"))

        changelist_url = reverse("admin:accounts_guardianrelationship_changelist")
        response = self.client.get(changelist_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vigente")
        self.assertContains(response, "Revocado")
        self.assertEqual(
            list(response.context["cl"].queryset.values_list("pk", flat=True)),
            [current.pk, former.pk],
        )
        self.assertEqual(
            list(
                self.client.get(f"{changelist_url}?estado=vigente")
                .context["cl"]
                .queryset.values_list("pk", flat=True)
            ),
            [current.pk],
        )
        self.assertEqual(
            list(
                self.client.get(f"{changelist_url}?estado=revocado")
                .context["cl"]
                .queryset.values_list("pk", flat=True)
            ),
            [former.pk],
        )

    def test_multiple_linking_skips_duplicates_and_preserves_revoked_history(self):
        guardian = User.objects.create_user("guardian@example.com", PASSWORD)
        already_linked = Student.objects.create(first_name="Sofía", last_name="Cianci")
        revoked_student = Student.objects.create(first_name="Juan", last_name="Cianci")
        new_student = Student.objects.create(first_name="Lucía", last_name="Cianci")
        not_selected = Student.objects.create(first_name="Mora", last_name="Cianci")
        GuardianRelationship.objects.create(
            guardian=guardian, student=already_linked, created_by=self.admin_user
        )
        GuardianRelationship.objects.create(
            guardian=guardian, student=not_selected, created_by=self.admin_user
        )
        old_link = GuardianRelationship.objects.create(
            guardian=guardian, student=revoked_student, created_by=self.admin_user
        )
        old_link.revoked_at = old_link.created_at
        old_link.revoked_by = self.admin_user
        old_link.save(update_fields=("revoked_at", "revoked_by"))

        response = self.client.post(
            reverse("admin:accounts_guardianrelationship_add"),
            {
                "guardian": guardian.pk,
                "students": [
                    already_linked.pk,
                    revoked_student.pk,
                    new_student.pk,
                ],
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Se crearon 2 vínculos vigentes.")
        self.assertContains(response, "Se omitió 1 vínculo que ya existía.")
        self.assertEqual(GuardianRelationship.objects.count(), 5)
        active_links = GuardianRelationship.objects.filter(
            guardian=guardian, revoked_at__isnull=True
        )
        self.assertEqual(active_links.count(), 4)
        self.assertEqual(
            set(active_links.values_list("student_id", flat=True)),
            {
                already_linked.pk,
                revoked_student.pk,
                new_student.pk,
                not_selected.pk,
            },
        )
        self.assertEqual(
            GuardianRelationship.objects.get(
                guardian=guardian, student=new_student
            ).created_by,
            self.admin_user,
        )

    def test_existing_enrollment_can_be_corrected_and_end_date_cleared(self):
        original_student = Student.objects.create(first_name="Ana", last_name="Cianci")
        corrected_student = Student.objects.create(first_name="Bea", last_name="Cianci")
        original_discipline = Discipline.objects.create(name="Jazz")
        corrected_discipline = Discipline.objects.create(name="Bachata")
        enrollment = Enrollment.objects.create(
            student=original_student,
            discipline=original_discipline,
            enrolled_at=date(2026, 1, 1),
            ended_at=date(2026, 2, 1),
        )
        historical = Enrollment.objects.create(
            student=original_student,
            discipline=corrected_discipline,
            enrolled_at=date(2025, 1, 1),
            ended_at=date(2025, 2, 1),
        )
        change_url = reverse("admin:academy_enrollment_change", args=(enrollment.pk,))

        self.assertContains(
            self.client.get(change_url),
            "Dejar vacío mientras el alumno continúe inscripto. Completar "
            "únicamente cuando se registre su baja. No utilizar para "
            "vencimientos de mensualidades",
        )
        response = self.client.post(
            change_url,
            {
                "student": corrected_student.pk,
                "discipline": corrected_discipline.pk,
                "enrolled_at": "2026-03-01",
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        enrollment.refresh_from_db()
        historical.refresh_from_db()
        self.assertEqual(enrollment.student_id, corrected_student.pk)
        self.assertEqual(enrollment.discipline_id, corrected_discipline.pk)
        self.assertEqual(enrollment.enrolled_at, date(2026, 3, 1))
        self.assertIsNone(enrollment.ended_at)
        self.assertEqual(Enrollment.objects.count(), 2)
        self.assertEqual(historical.ended_at, date(2025, 2, 1))

    def test_editing_enrollment_rejects_an_active_duplicate(self):
        first_student = Student.objects.create(first_name="Ana", last_name="Cianci")
        second_student = Student.objects.create(first_name="Bea", last_name="Cianci")
        discipline = Discipline.objects.create(name="Jazz")
        existing = Enrollment.objects.create(
            student=first_student, discipline=discipline
        )
        target = Enrollment.objects.create(
            student=second_student, discipline=discipline
        )

        response = self.client.post(
            reverse("admin:academy_enrollment_change", args=(target.pk,)),
            {
                "student": first_student.pk,
                "discipline": discipline.pk,
                "enrolled_at": target.enrolled_at.isoformat(),
                "ended_at": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["adminform"].form.errors)
        self.assertEqual(Enrollment.objects.count(), 2)
        existing.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(existing.student_id, first_student.pk)
        self.assertEqual(target.student_id, second_student.pk)

    def test_admin_rejects_future_enrollment_end_date(self):
        student = Student.objects.create(first_name="Sol", last_name="Cianci")
        discipline = Discipline.objects.create(name="Clásico")
        enrollment = Enrollment.objects.create(
            student=student, discipline=discipline, enrolled_at=date(2026, 1, 1)
        )

        with patch("academy.admin.timezone.localdate", return_value=date(2026, 10, 25)):
            response = self.client.post(
                reverse("admin:academy_enrollment_change", args=(enrollment.pk,)),
                {
                    "student": student.pk,
                    "discipline": discipline.pk,
                    "enrolled_at": "2026-01-01",
                    "ended_at": "2026-10-26",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "La fecha de baja no puede ser futura.")
        enrollment.refresh_from_db()
        self.assertIsNone(enrollment.ended_at)

    def test_inactive_discipline_is_not_enrollable_and_deactivation_keeps_history(self):
        student = Student.objects.create(first_name="Sol", last_name="Cianci")
        inactive = Discipline.objects.create(name="Jazz", is_active=False)
        add_url = reverse("admin:academy_enrollment_add")
        inactive_response = self.client.post(
            add_url,
            {
                "student": student.pk,
                "discipline": inactive.pk,
                "enrolled_at": date.today().isoformat(),
                "ended_at": "",
            },
        )
        self.assertEqual(inactive_response.status_code, 200)
        self.assertFalse(Enrollment.objects.exists())

        active = Discipline.objects.create(name="Clásico")
        response = self.client.post(
            add_url,
            {
                "student": student.pk,
                "discipline": active.pk,
                "enrolled_at": date.today().isoformat(),
                "ended_at": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        enrollment = Enrollment.objects.get(student=student, discipline=active)

        response = self.client.post(
            reverse("admin:academy_discipline_change", args=(active.pk,)),
            {
                "name": active.name,
                "is_active": "",
                "class_schedules-TOTAL_FORMS": "0",
                "class_schedules-INITIAL_FORMS": "0",
            },
        )
        self.assertEqual(response.status_code, 302)
        active.refresh_from_db()
        enrollment.refresh_from_db()
        self.assertFalse(active.is_active)
        self.assertIsNone(enrollment.ended_at)

    def test_students_and_disciplines_cannot_be_deleted_but_unbilled_enrollment_can(
        self,
    ):
        student = Student.objects.create(first_name="Eva", last_name="Cianci")
        discipline = Discipline.objects.create(name="Bachata")
        enrollment = Enrollment.objects.create(student=student, discipline=discipline)
        request = RequestFactory().get("/admin/")
        request.user = self.admin_user
        for model, obj in ((Student, student), (Discipline, discipline)):
            model_admin = admin.site._registry[model]
            self.assertFalse(model_admin.has_delete_permission(request, obj))

        enrollment_admin = admin.site._registry[Enrollment]
        self.assertTrue(enrollment_admin.has_delete_permission(request, enrollment))
