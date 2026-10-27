from calendar import monthrange
from datetime import date
from urllib.parse import urlencode

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from billing.models import DisciplinePrice, MonthlyCharge, Scholarship
from billing.services import generate_monthly_charges
from core.money import format_ars_amount

from .models import ClassSchedule, Discipline, Enrollment, Student, Teacher


class ScholarshipInline(admin.TabularInline):
    model = Scholarship
    fields = (
        "discipline",
        "percentage",
        "start_month",
        "end_month",
        "created_at",
        "created_by",
    )
    readonly_fields = ("created_at", "created_by")
    autocomplete_fields = ("discipline",)
    extra = 0
    can_delete = False


class ClassScheduleInline(admin.TabularInline):
    model = ClassSchedule
    fields = ("weekday", "start_time", "end_time", "teacher", "is_active")
    autocomplete_fields = ("teacher",)
    extra = 0


class TeacherScheduleInline(admin.TabularInline):
    model = ClassSchedule
    fields = ("discipline", "weekday", "start_time", "end_time", "is_active")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("first_name", "last_name")
    fields = ("first_name", "last_name", "is_active")
    inlines = (TeacherScheduleInline,)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "date_of_birth", "user")
    search_fields = ("first_name", "last_name", "user__email")
    autocomplete_fields = ("user",)
    fields = ("first_name", "last_name", "date_of_birth", "user")
    inlines = (ScholarshipInline,)

    def save_formset(self, request, form, formset, change):
        if formset.model is not Scholarship:
            return super().save_formset(request, form, formset, change)

        scholarships = formset.save(commit=False)
        for scholarship in scholarships:
            if not scholarship.pk:
                scholarship.created_by = request.user
            scholarship.save()
        for deleted_scholarship in formset.deleted_objects:
            deleted_scholarship.delete()
        formset.save_m2m()

    def has_delete_permission(self, request, obj=None):
        return False


class DisciplineAdminForm(forms.ModelForm):
    initial_monthly_price = forms.DecimalField(
        label=_("Precio mensual inicial"),
        required=False,
        min_value=0.01,
        max_digits=12,
        decimal_places=2,
        help_text=_(
            "Ingresá pesos enteros o hasta dos decimales con punto, "
            "por ejemplo 30000 o 30000.50. Dejá vacío si todavía no "
            "definiste el precio."
        ),
    )
    initial_price_effective_month = forms.DateField(
        label=_("Vigente desde el mes"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text=_("Usá el primer día del mes; podés indicar un mes futuro."),
    )

    class Meta:
        model = Discipline
        fields = ("name", "is_active")

    def clean(self):
        cleaned_data = super().clean()
        initial_monthly_price = cleaned_data.get("initial_monthly_price")
        effective_month = cleaned_data.get("initial_price_effective_month")
        if initial_monthly_price is not None and effective_month is None:
            self.add_error(
                "initial_price_effective_month",
                _("Indicá desde qué mes se aplica el precio."),
            )
        if initial_monthly_price is None and effective_month is not None:
            self.add_error(
                "initial_monthly_price",
                _("Ingresá el precio mensual o dejá también vacía la vigencia."),
            )
        if effective_month and effective_month.day != 1:
            self.add_error(
                "initial_price_effective_month",
                _("La vigencia debe comenzar el primer día del mes."),
            )
        return cleaned_data


@admin.register(Discipline)
class DisciplineAdmin(admin.ModelAdmin):
    form = DisciplineAdminForm
    list_display = ("name", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    inlines = (ClassScheduleInline,)

    def get_fields(self, request, obj=None):
        fields = ["name", "is_active"]
        if obj is None and request.user.has_perm("billing.add_disciplineprice"):
            fields.extend(("initial_monthly_price", "initial_price_effective_month"))
        return fields

    def get_queryset(self, request):
        current_month = timezone.localdate().replace(day=1)
        current_price_amount = (
            DisciplinePrice.objects.filter(
                discipline_id=OuterRef("pk"),
                effective_month__lte=current_month,
            )
            .order_by("-effective_month")
            .values("amount")[:1]
        )
        return super().get_queryset(request).annotate(
            current_price_amount=Subquery(
                current_price_amount,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )

    def get_list_display(self, request):
        columns = list(super().get_list_display(request))
        if request.user.has_perm("billing.view_disciplineprice"):
            columns.extend(("current_monthly_price", "price_history_link"))
        if request.user.has_perm("billing.add_disciplineprice"):
            columns.append("add_price_link")
        return columns

    @admin.display(description=_("Precio mensual vigente"))
    def current_monthly_price(self, discipline):
        if discipline.current_price_amount is None:
            return _("Sin tarifa vigente")
        return _("%(amount)s por mes") % {
            "amount": format_ars_amount(discipline.current_price_amount)
        }

    @admin.display(description=_("Tarifas"))
    def price_history_link(self, discipline):
        price_list_url = reverse("admin:billing_disciplineprice_changelist")
        price_filters = urlencode({"discipline__id__exact": discipline.pk})
        price_list_url = f"{price_list_url}?{price_filters}"
        return format_html('<a href="{}">{}</a>', price_list_url, _("Historial"))

    @admin.display(description=_("Tarifas"))
    def add_price_link(self, discipline):
        new_price_url = reverse("admin:billing_disciplineprice_add")
        new_price_url = f"{new_price_url}?{urlencode({'discipline': discipline.pk})}"
        return format_html('<a href="{}">{}</a>', new_price_url, _("Agregar tarifa"))

    def save_model(self, request, discipline, form, change):
        """Save a discipline and its optional starting price as one admin action."""
        with transaction.atomic():
            super().save_model(request, discipline, form, change)
            initial_monthly_price = form.cleaned_data.get("initial_monthly_price")
            effective_month = form.cleaned_data.get("initial_price_effective_month")
            if initial_monthly_price is not None:
                if effective_month is None or effective_month.day != 1:
                    raise ValidationError(
                        _("Indicá el primer día del mes desde el que rige el precio.")
                    )
                DisciplinePrice.objects.create(
                    discipline=discipline,
                    amount=initial_monthly_price,
                    effective_month=effective_month,
                    created_by=request.user,
                )

    def has_delete_permission(self, request, obj=None):
        return False


class EnrollmentAdminForm(forms.ModelForm):
    initial_monthly_charge_notice = forms.CharField(
        label=_("Mensualidad inicial"),
        required=False,
        disabled=True,
        initial=_(
            "Si la fecha de inicio ya comenzó y la inscripción cubre algún día "
            "del mes actual, se generará el cargo completo por la tarifa vigente "
            "indicada junto a la disciplina. Las altas futuras no generan cargos "
            "automáticamente."
        ),
    )

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
        if self.instance.pk:
            Enrollment.objects.select_for_update().only("pk").get(pk=self.instance.pk)
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

        if (
            self.instance.pk
            and MonthlyCharge.objects.filter(enrollment_id=self.instance.pk).exists()
        ):
            changed_protected_fields = any(
                cleaned_data.get(field) != getattr(self.instance, field)
                for field in ("student", "discipline", "enrolled_at")
                if field in cleaned_data
            )
            if changed_protected_fields:
                self.add_error(
                    None,
                    _(
                        "No se pueden modificar el alumno, la disciplina ni la fecha "
                        "de inscripción porque ya existen cargos asociados."
                    ),
                )
        return cleaned_data


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    form = EnrollmentAdminForm
    list_display = ("student", "discipline", "enrolled_at", "ended_at")
    list_filter = ("discipline", "ended_at")
    search_fields = ("student__first_name", "student__last_name", "discipline__name")
    autocomplete_fields = ("student",)
    actions = ("end_enrollments_today",)
    fields = ("student", "discipline", "enrolled_at", "ended_at")

    def get_fields(self, request, obj=None):
        fields = ["student", "discipline", "enrolled_at", "ended_at"]
        if obj is None:
            fields.append("initial_monthly_charge_notice")
        return fields

    def get_form(self, request, obj=None, **kwargs):
        enrollment_form = super().get_form(request, obj, **kwargs)
        if (
            obj is None
            and "initial_monthly_charge_notice" in enrollment_form.base_fields
        ):
            enrollment_form.base_fields[
                "initial_monthly_charge_notice"
            ].initial = self.get_monthly_charge_notice(request)
        return enrollment_form

    @staticmethod
    def get_monthly_charge_notice(request):
        if not request.user.has_perm("billing.add_monthlycharge"):
            return _(
                "La inscripción se guardará sin generar una mensualidad. "
                "El cargo puede generarlo personal con permiso de facturación."
            )
        if not request.user.has_perm("billing.view_disciplineprice"):
            return _(
                "Si la fecha ya comenzó y la inscripción cubre el mes actual, "
                "el sistema generará el cargo completo con la tarifa vigente."
            )
        return _(
            "Si la fecha de inicio ya comenzó y la inscripción cubre algún día "
            "del mes actual, se generará el cargo completo por la tarifa vigente "
            "indicada junto a la disciplina. Las altas futuras no generan cargos "
            "automáticamente."
        )

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "discipline":
            is_adding_enrollment = not request.resolver_match.kwargs.get("object_id")
            if is_adding_enrollment:
                active_disciplines = Discipline.objects.filter(is_active=True)
                can_view_prices = request.user.has_perm("billing.view_disciplineprice")
                if can_view_prices:
                    current_month = timezone.localdate().replace(day=1)
                    current_price_amount = (
                        DisciplinePrice.objects.filter(
                            discipline_id=OuterRef("pk"),
                            effective_month__lte=current_month,
                        )
                        .order_by("-effective_month")
                        .values("amount")[:1]
                    )
                    active_disciplines = active_disciplines.annotate(
                        current_price_amount=Subquery(
                            current_price_amount,
                            output_field=DecimalField(
                                max_digits=12, decimal_places=2
                            ),
                        )
                    )
                kwargs["queryset"] = active_disciplines
            discipline_field = super().formfield_for_foreignkey(
                db_field, request, **kwargs
            )
            if (
                is_adding_enrollment
                and request.user.has_perm("billing.view_disciplineprice")
                and discipline_field is not None
            ):
                discipline_field.label_from_instance = self.discipline_choice_label
            return discipline_field
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @staticmethod
    def discipline_choice_label(discipline):
        if discipline.current_price_amount is None:
            return _("%(discipline)s — sin tarifa para el mes actual") % {
                "discipline": discipline.name
            }
        monthly_price = format_ars_amount(discipline.current_price_amount)
        return _("%(discipline)s — %(price)s por mes") % {
            "discipline": discipline.name,
            "price": monthly_price,
        }

    def save_model(self, request, enrollment, form, change):
        """Save new enrollment charges atomically when they cover the current month."""
        is_new_enrollment = not change
        with transaction.atomic():
            super().save_model(request, enrollment, form, change)
            if not is_new_enrollment:
                return
            if not request.user.has_perm("billing.add_monthlycharge"):
                self.message_user(
                    request,
                    _(
                        "La inscripción se guardó. No se generó la mensualidad "
                        "porque tu usuario no tiene permiso para emitir cargos."
                    ),
                    messages.WARNING,
                )
                return

            today = timezone.localdate()
            billing_period = today.replace(day=1)
            last_day = date(
                billing_period.year,
                billing_period.month,
                monthrange(billing_period.year, billing_period.month)[1],
            )
            if enrollment.enrolled_at > today or enrollment.enrolled_at > last_day:
                return
            if enrollment.ended_at and enrollment.ended_at < billing_period:
                return

            generation_result = generate_monthly_charges(
                billing_period=billing_period,
                enrollment_ids=(enrollment.pk,),
            )
            if generation_result.created:
                self.message_user(
                    request,
                    _("Se generó la mensualidad de este mes por la tarifa vigente."),
                    messages.SUCCESS,
                )
            elif generation_result.missing_prices:
                self.message_user(
                    request,
                    _(
                        "La inscripción se guardó, pero no se generó su mensualidad "
                        "porque la disciplina no tiene una tarifa vigente."
                    ),
                    messages.WARNING,
                )

    def get_readonly_fields(self, request, obj=None):
        if obj and MonthlyCharge.objects.filter(enrollment_id=obj.pk).exists():
            return ("student", "discipline", "enrolled_at")
        return ()

    def has_delete_permission(self, request, obj=None):
        if obj and MonthlyCharge.objects.filter(enrollment_id=obj.pk).exists():
            return False
        return super().has_delete_permission(request, obj)

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
