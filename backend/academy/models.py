from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Student(models.Model):
    first_name = models.CharField(_("Nombre"), max_length=150)
    last_name = models.CharField(_("Apellido"), max_length=150)
    date_of_birth = models.DateField(_("Fecha de nacimiento"), null=True, blank=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Cuenta de usuario"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="student_record",
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Última modificación"), auto_now=True)

    class Meta:
        verbose_name = _("Alumno")
        verbose_name_plural = _("Alumnos")
        ordering = ("last_name", "first_name", "pk")

    @property
    def guardians(self):
        user_model = apps.get_model(settings.AUTH_USER_MODEL)
        return user_model.objects.filter(
            guardian_relationships__student_id=self.pk,
            guardian_relationships__revoked_at__isnull=True,
        )

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class Discipline(models.Model):
    name = models.CharField(_("Nombre"), max_length=120)
    is_active = models.BooleanField(_("Activa"), default=True)
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Última modificación"), auto_now=True)

    class Meta:
        verbose_name = _("Disciplina")
        verbose_name_plural = _("Disciplinas")
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="academy_discipline_name_ci_unique"
            )
        ]

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": _("Ingresá el nombre de la disciplina.")})

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Enrollment(models.Model):
    student = models.ForeignKey(
        Student,
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    discipline = models.ForeignKey(
        Discipline,
        verbose_name=_("Disciplina"),
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    enrolled_at = models.DateField(
        _("Fecha de inscripción"), default=timezone.localdate
    )
    ended_at = models.DateField(_("Fecha de baja"), null=True, blank=True)

    class Meta:
        verbose_name = _("Inscripción")
        verbose_name_plural = _("Inscripciones")
        ordering = ("-enrolled_at", "-pk")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "discipline"),
                condition=Q(ended_at__isnull=True),
                name="academy_active_enrollment_unique",
            ),
            models.CheckConstraint(
                condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("enrolled_at")),
                name="academy_enrollment_end_after_start",
            ),
        ]

    def clean(self):
        super().clean()
        if self.ended_at and self.enrolled_at and self.ended_at < self.enrolled_at:
            raise ValidationError(
                {"ended_at": _("La fecha de baja no puede ser anterior al alta.")}
            )
        if (
            self._state.adding
            and self.ended_at is None
            and self.discipline_id
            and not self.discipline.is_active
        ):
            raise ValidationError(
                {"discipline": _("No se puede inscribir en una disciplina inactiva.")}
            )

    def __str__(self):
        return f"{self.student} — {self.discipline}"
