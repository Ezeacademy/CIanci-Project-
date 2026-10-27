from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import F, Q
from django.db.models.deletion import ProtectedError
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


class Teacher(models.Model):
    first_name = models.CharField(_("Nombre"), max_length=150)
    last_name = models.CharField(_("Apellido"), max_length=150)
    is_active = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Profesor")
        verbose_name_plural = _("Profesores")
        ordering = ("last_name", "first_name", "pk")

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()


class ClassSchedule(models.Model):
    WEEKDAYS = (
        (0, _("Lunes")),
        (1, _("Martes")),
        (2, _("Miércoles")),
        (3, _("Jueves")),
        (4, _("Viernes")),
        (5, _("Sábado")),
        (6, _("Domingo")),
    )

    discipline = models.ForeignKey(
        Discipline,
        verbose_name=_("Disciplina"),
        on_delete=models.PROTECT,
        related_name="class_schedules",
    )
    teacher = models.ForeignKey(
        Teacher,
        verbose_name=_("Profesor"),
        on_delete=models.PROTECT,
        related_name="class_schedules",
    )
    weekday = models.PositiveSmallIntegerField(_("Día"), choices=WEEKDAYS)
    start_time = models.TimeField(_("Desde"))
    end_time = models.TimeField(_("Hasta"))
    is_active = models.BooleanField(_("Activo"), default=True)

    class Meta:
        verbose_name = _("Horario semanal")
        verbose_name_plural = _("Horarios semanales")
        ordering = ("weekday", "start_time", "discipline__name", "pk")
        constraints = [
            models.CheckConstraint(
                condition=Q(weekday__in=tuple(range(7))),
                name="academy_schedule_weekday_valid",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="academy_schedule_end_after_start",
            ),
            models.UniqueConstraint(
                fields=("discipline", "weekday", "start_time", "end_time"),
                condition=Q(is_active=True),
                name="academy_active_schedule_slot_unique",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": _("La hora de finalización debe ser posterior al inicio.")}
            )
        if self.weekday not in range(7):
            raise ValidationError({"weekday": _("Elegí un día válido de la semana.")})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.discipline} — {self.get_weekday_display()} {self.start_time:%H:%M}"
        )


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
            self.pk
            and self.ended_at
            and apps.get_model("billing", "MonthlyCharge")
            .objects.filter(
                enrollment_id=self.pk,
                period__gt=self.ended_at.replace(day=1),
            )
            .exists()
        ):
            raise ValidationError(
                {
                    "ended_at": _(
                        "La fecha de baja no puede ser anterior al inicio "
                        "de un período con cargos emitidos."
                    )
                }
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

    def save(self, *args, **kwargs):
        # QuerySet.update()/bulk_update() bypass this guard; current writes use save().
        protected_fields = {"student", "discipline", "enrolled_at"}
        if kwargs.get("update_fields") is not None:
            protected_fields &= set(kwargs["update_fields"])

        with transaction.atomic():
            if self.pk:
                previous = Enrollment.objects.select_for_update().get(pk=self.pk)
                changed = any(
                    (getattr(self, f"{field}_id") != getattr(previous, f"{field}_id"))
                    if field in {"student", "discipline"}
                    else getattr(self, field) != getattr(previous, field)
                    for field in protected_fields
                )
                ended_at_is_being_saved = (
                    kwargs.get("update_fields") is None
                    or "ended_at" in kwargs["update_fields"]
                )
                effective_ended_at = (
                    self.ended_at if ended_at_is_being_saved else previous.ended_at
                )
                if (
                    effective_ended_at
                    and apps.get_model("billing", "MonthlyCharge")
                    .objects.filter(
                        enrollment_id=self.pk,
                        period__gt=effective_ended_at.replace(day=1),
                    )
                    .exists()
                ):
                    raise ValidationError(
                        {
                            "ended_at": _(
                                "La fecha de baja no puede ser anterior al inicio "
                                "de un período con cargos emitidos."
                            )
                        }
                    )
                if (
                    changed
                    and apps.get_model("billing", "MonthlyCharge")
                    .objects.filter(enrollment_id=self.pk)
                    .exists()
                ):
                    raise ValidationError(
                        _(
                            "No se pueden modificar el alumno, la disciplina ni "
                            "la fecha "
                            "de inscripción cuando existen cargos asociados."
                        )
                    )
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            Enrollment.objects.select_for_update().get(pk=self.pk)
            charges = apps.get_model("billing", "MonthlyCharge").objects.filter(
                enrollment_id=self.pk
            )
            if charges.exists():
                raise ProtectedError(
                    _("No se puede eliminar una inscripción con cargos asociados."),
                    charges,
                )
            return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.student} — {self.discipline}"
