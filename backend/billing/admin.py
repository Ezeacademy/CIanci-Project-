from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.money import format_ars_amount

from .models import DisciplinePrice, MonthlyCharge
from .services import generate_monthly_charges, get_monthly_charge_period_summary

MONTH_NAMES = (
    _("Enero"),
    _("Febrero"),
    _("Marzo"),
    _("Abril"),
    _("Mayo"),
    _("Junio"),
    _("Julio"),
    _("Agosto"),
    _("Septiembre"),
    _("Octubre"),
    _("Noviembre"),
    _("Diciembre"),
)


class BillingPeriodForm(forms.Form):
    month = forms.ChoiceField(
        label=_("Mes"),
        choices=tuple(
            (str(month_number), month_name)
            for month_number, month_name in enumerate(MONTH_NAMES, 1)
        ),
    )
    year = forms.IntegerField(label=_("Año"), min_value=1, max_value=9999)

    def clean(self):
        cleaned_data = super().clean()
        month_number = cleaned_data.get("month")
        year_number = cleaned_data.get("year")
        if month_number and year_number:
            cleaned_data["billing_period"] = date(year_number, int(month_number), 1)
        return cleaned_data


@admin.register(DisciplinePrice)
class DisciplinePriceAdmin(admin.ModelAdmin):
    list_display = (
        "discipline",
        "formatted_amount",
        "currency",
        "effective_month",
        "created_at",
        "created_by",
    )
    list_filter = ("discipline", "currency")
    search_fields = ("discipline__name",)
    autocomplete_fields = ("discipline",)
    fields = (
        "discipline",
        "amount",
        "currency",
        "effective_month",
        "created_at",
        "created_by",
    )
    readonly_fields = ("created_at", "created_by")

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.monthly_charges.exists():
            readonly_fields.extend(
                (
                    "discipline",
                    "formatted_amount",
                    "currency",
                    "effective_month",
                )
            )
        return tuple(readonly_fields)

    def get_form(self, request, obj=None, **kwargs):
        price_form = super().get_form(request, obj, **kwargs)
        if "amount" in price_form.base_fields:
            price_form.base_fields["amount"].help_text = _(
                "Ingresá pesos enteros o hasta dos decimales con punto, "
                "por ejemplo 30000 o 30000.50."
            )
        return price_form

    def get_fields(self, request, obj=None):
        fields = list(super().get_fields(request, obj))
        if obj and obj.monthly_charges.exists():
            fields = [
                "formatted_amount" if field_name == "amount" else field_name
                for field_name in fields
            ]
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description=_("Importe"), ordering="amount")
    def formatted_amount(self, discipline_price):
        return format_ars_amount(discipline_price.amount)

    def get_changeform_initial_data(self, request):
        initial_data = super().get_changeform_initial_data(request)
        discipline_id = request.GET.get("discipline")
        if discipline_id:
            initial_data["discipline"] = discipline_id
        return initial_data

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MonthlyCharge)
class MonthlyChargeAdmin(admin.ModelAdmin):
    change_list_template = "admin/billing/monthlycharge/change_list.html"
    list_display = (
        "student",
        "discipline",
        "period",
        "formatted_base_amount",
        "scholarship_percentage_display",
        "formatted_discount_amount",
        "formatted_amount",
        "paid_amount",
        "outstanding_balance",
        "currency",
    )
    list_filter = ("period", "discipline", "currency")
    search_fields = ("student__first_name", "student__last_name", "discipline__name")
    ordering = ("-period", "student__last_name", "student__first_name")
    readonly_fields = (
        "student",
        "discipline",
        "enrollment",
        "period",
        "formatted_price_applied",
        "formatted_base_amount",
        "scholarship_percentage_display",
        "formatted_discount_amount",
        "formatted_amount",
        "currency",
        "created_at",
    )
    fields = readonly_fields

    def get_queryset(self, request):
        decimal_field = DecimalField(max_digits=12, decimal_places=2)
        return (
            super()
            .get_queryset(request)
            .annotate(
                applied_amount=Coalesce(
                    Sum("payment_allocations__amount"),
                    Value(Decimal("0.00"), output_field=decimal_field),
                    output_field=decimal_field,
                )
            )
        )

    @admin.display(description=_("Pagado"))
    def paid_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.applied_amount)

    @admin.display(description=_("Saldo pendiente"))
    def outstanding_balance(self, monthly_charge):
        return format_ars_amount(
            monthly_charge.amount - monthly_charge.applied_amount
        )

    @admin.display(description=_("Importe"), ordering="amount")
    def formatted_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.amount)

    @admin.display(description=_("Precio base"), ordering="base_amount")
    def formatted_base_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.base_amount)

    @admin.display(description=_("Beca aplicada"), ordering="scholarship_percentage")
    def scholarship_percentage_display(self, monthly_charge):
        if monthly_charge.scholarship_percentage is None:
            return "—"
        return _("%(percentage)s %%") % {
            "percentage": monthly_charge.scholarship_percentage
        }

    @admin.display(description=_("Descuento"), ordering="discount_amount")
    def formatted_discount_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.discount_amount)

    @admin.display(description=_("Tarifa aplicada"))
    def formatted_price_applied(self, monthly_charge):
        return format_ars_amount(monthly_charge.price_applied.amount)

    def get_urls(self):
        management_urls = [
            path(
                "management/",
                self.admin_site.admin_view(self.monthly_charge_management_view),
                name="billing_monthlycharge_management",
            )
        ]
        return management_urls + super().get_urls()

    def monthly_charge_management_view(self, request):
        """Preview or generate a billing period through the shared billing service."""
        if not self.has_view_permission(request):
            raise PermissionDenied

        today = timezone.localdate()
        initial_values = {"month": str(today.month), "year": today.year}
        if request.method == "POST":
            if not request.user.has_perm("billing.add_monthlycharge"):
                raise PermissionDenied
            billing_period_form = BillingPeriodForm(request.POST)
            if billing_period_form.is_valid():
                billing_period = billing_period_form.cleaned_data["billing_period"]
                generation_result = generate_monthly_charges(
                    billing_period=billing_period
                )
                self.message_user(
                    request,
                    _(
                        "Período %(period)s — creadas: %(created)s; existentes "
                        "o ya resueltas: %(existing)s; omitidas: %(omitted)s."
                    )
                    % {
                        "period": billing_period.strftime("%m/%Y"),
                        "created": generation_result.created,
                        "existing": generation_result.existing,
                        "omitted": generation_result.omitted,
                    },
                    messages.SUCCESS if generation_result.created else messages.INFO,
                )
                if generation_result.missing_prices:
                    missing_disciplines = ", ".join(
                        sorted(
                            {
                                discipline_name
                                for _student_name, discipline_name
                                in generation_result.missing_prices
                            }
                        )
                    )
                    self.message_user(
                        request,
                        _(
                            "No se generaron cargos para estas disciplinas porque "
                            "no tienen una tarifa aplicable: %(disciplines)s."
                        )
                        % {"disciplines": missing_disciplines},
                        messages.WARNING,
                    )
                if generation_result.eligibility_changed:
                    self.message_user(
                        request,
                        _(
                            "Se omitieron %(count)s inscripciones que dejaron de "
                            "corresponder al período durante la operación."
                        )
                        % {"count": len(generation_result.eligibility_changed)},
                        messages.WARNING,
                    )
                management_url = reverse("admin:billing_monthlycharge_management")
                return HttpResponseRedirect(
                    f"{management_url}?month={billing_period.month}"
                    f"&year={billing_period.year}"
                )
        else:
            billing_period_form = BillingPeriodForm(
                request.GET or initial_values,
                initial=initial_values,
            )

        period_summary = None
        if billing_period_form.is_valid():
            period_summary = get_monthly_charge_period_summary(
                billing_period=billing_period_form.cleaned_data["billing_period"]
            )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Gestión de mensualidades"),
            "billing_period_form": billing_period_form,
            "period_summary": period_summary,
            "can_generate": request.user.has_perm("billing.add_monthlycharge"),
            "monthly_charge_list_url": reverse(
                "admin:billing_monthlycharge_changelist"
            ),
        }
        return TemplateResponse(
            request,
            "admin/billing/monthly_charge_management.html",
            context,
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)
