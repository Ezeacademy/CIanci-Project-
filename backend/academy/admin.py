from django import forms
from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import Discipline, Enrollment, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "date_of_birth", "user")
    search_fields = ("first_name", "last_name", "user__email")
    autocomplete_fields = ("user",)
    fields = ("first_name", "last_name", "date_of_birth", "user")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    fields = ("name", "is_active")

    def has_delete_permission(self, request, obj=None):
        return False


class EnrollmentAdminForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ("student", "discipline", "enrolled_at", "ended_at")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ended_at"].help_text = _(
            "Dejar vacío mientras el alumno continúe inscripto. Completar "
            "únicamente cuando se registre su baja. No utilizar para "
            "vencimientos de mensualidades"
        )

    def clean(self):
        cleaned_data = super().clean()
        ended_at = cleaned_data.get("ended_at")
        if ended_at and ended_at > timezone.localdate():
            self.add_error(
                "ended_at",
                _("La fecha de baja no puede ser futura."),
            )

        if self.instance._state.adding and "discipline" in cleaned_data:
            discipline = (
                Discipline.objects.select_for_update()
                .filter(pk=cleaned_data["discipline"].pk)
                .first()
            )
            if discipline is None or not discipline.is_active:
                self.add_error(
                    "discipline",
                    _("No se puede inscribir en una disciplina inactiva."),
                )
            else:
                cleaned_data["discipline"] = discipline
        return cleaned_data


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    form = EnrollmentAdminForm
    list_display = ("student", "discipline", "enrolled_at", "ended_at")
    list_filter = ("discipline", "ended_at")
    search_fields = ("student__first_name", "student__last_name", "discipline__name")
    autocomplete_fields = ("student", "discipline")
    actions = ("end_enrollments_today",)
    fields = ("student", "discipline", "enrolled_at", "ended_at")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "discipline" and not request.resolver_match.kwargs.get(
            "object_id"
        ):
            kwargs["queryset"] = Discipline.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Dar de baja hoy las inscripciones seleccionadas"))
    def end_enrollments_today(self, request, queryset):
        ended_at = timezone.localdate()
        with transaction.atomic():
            enrollments = queryset.select_for_update().filter(ended_at__isnull=True)
            for enrollment in enrollments:
                enrollment.ended_at = ended_at
                enrollment.save(update_fields=("ended_at",))
                self.log_change(
                    request,
                    enrollment,
                    [{"changed": {"fields": ["ended_at"]}}],
                )
        self.message_user(
            request,
            _("Las inscripciones seleccionadas fueron dadas de baja."),
            messages.SUCCESS,
        )
