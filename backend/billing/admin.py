from datetime import date
from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.money import format_ars_amount

from .adjustments import confirm_charge_adjustment, preview_charge_adjustment
from .models import ChargeAdjustment, DisciplinePrice, MonthlyCharge
from .queries import charges_with_economic_totals
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


class ChargeAdjustmentForm(forms.Form):
    resulting_amount = forms.DecimalField(
        label=_("Nuevo total"),
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        help_text=_(
            "Ingresá el total correcto. Para anular económicamente, ingresá 0."
        ),
    )
    reason = forms.CharField(
        label=_("Motivo interno"),
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    reverses = forms.ModelChoiceField(
        label=_("Compensar un ajuste anterior (opcional)"),
        queryset=ChargeAdjustment.objects.none(),
        required=False,
        help_text=_(
            "Al compensar, el nuevo total se calcula automáticamente; "
            "no se recupera crédito disponible."
        ),
    )

    def __init__(self, *args, charge, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reverses"].queryset = charge.adjustments.filter(
            reversal__isnull=True
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("resulting_amount") is None and cleaned.get("reverses") is None:
            raise ValidationError(
                _("Ingresá el nuevo total o seleccioná un ajuste para compensar.")
            )
        return cleaned


class ChargeAdjustmentInline(admin.TabularInline):
    model = ChargeAdjustment
    fields = (
        "created_at",
        "previous_total",
        "new_total",
        "formatted_difference",
        "reason",
        "created_by",
        "reverses",
    )
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm(
            "billing.view_monthlycharge"
        ) or request.user.has_perm("billing.adjust_monthlycharge")

    @admin.display(description=_("Total anterior"))
    def previous_total(self, adjustment):
        return format_ars_amount(adjustment.previous_amount)

    @admin.display(description=_("Total resultante"))
    def new_total(self, adjustment):
        return format_ars_amount(adjustment.resulting_amount)

    @admin.display(description=_("Diferencia"))
    def formatted_difference(self, adjustment):
        return format_ars_amount(adjustment.difference)


@admin.register(MonthlyCharge)
class MonthlyChargeAdmin(admin.ModelAdmin):
    change_list_template = "admin/billing/monthlycharge/change_list.html"
    change_form_template = "admin/billing/monthlycharge/change_form.html"
    inlines = (ChargeAdjustmentInline,)
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
        "original_amount",
        "formatted_amount",
        "paid_amount",
        "released_amount",
        "outstanding_balance",
        "currency",
        "created_at",
    )
    fields = readonly_fields

    def get_queryset(self, request):
        return charges_with_economic_totals(super().get_queryset(request))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        return super().change_view(
            request,
            object_id,
            form_url,
            {
                **(extra_context or {}),
                "can_adjust": request.user.has_perm("billing.adjust_monthlycharge"),
            },
        )

    @admin.display(description=_("Pagado"))
    def paid_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.paid_amount)

    @admin.display(description=_("Saldo pendiente"))
    def outstanding_balance(self, monthly_charge):
        return format_ars_amount(monthly_charge.outstanding)

    @admin.display(description=_("Total actual"), ordering="current_amount")
    def formatted_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.current_amount)

    @admin.display(description=_("Importe original"))
    def original_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.amount)

    @admin.display(description=_("Liberado como saldo a favor"))
    def released_amount(self, monthly_charge):
        return format_ars_amount(monthly_charge.released_amount)

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
                "<int:object_id>/adjust/",
                self.admin_site.admin_view(self.adjust_charge_view),
                name="billing_monthlycharge_adjust",
            ),
            path(
                "management/",
                self.admin_site.admin_view(self.monthly_charge_management_view),
                name="billing_monthlycharge_management",
            ),
        ]
        return management_urls + super().get_urls()

    def adjust_charge_view(self, request, object_id):
        """Require an explicit signed preview before an audited correction."""
        if not request.user.has_perm("billing.adjust_monthlycharge"):
            raise PermissionDenied
        charge = self.get_object(request, object_id)
        if charge is None or not self.has_view_permission(request, charge):
            raise PermissionDenied
        form = ChargeAdjustmentForm(request.POST or None, charge=charge)
        preview = None
        if request.method == "POST":
            try:
                if "_confirm" in request.POST:
                    adjustment = confirm_charge_adjustment(
                        preview_token=request.POST.get("preview_token", ""),
                        actor=request.user,
                        charge_id=charge.pk,
                    )
                    self.message_user(
                        request,
                        _(
                            "El ajuste quedó registrado. "
                            "Los pagos originales se conservaron."
                        ),
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(
                        reverse(
                            "admin:billing_monthlycharge_change",
                            args=(adjustment.charge_id,),
                        )
                    )
                if form.is_valid():
                    reverses = form.cleaned_data["reverses"]
                    preview = preview_charge_adjustment(
                        charge_id=charge.pk,
                        resulting_amount=form.cleaned_data["resulting_amount"],
                        reason=form.cleaned_data["reason"],
                        actor=request.user,
                        reverses_id=reverses.pk if reverses else None,
                    )
            except ValidationError as exc:
                form.is_valid()
                form.add_error(None, "; ".join(exc.messages))
        charge = self.get_queryset(request).get(pk=charge.pk)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": charge,
            "title": _("Ajustar mensualidad"),
            "form": form,
            "preview_token": preview["token"] if preview else None,
            "preview": {
                key: format_ars_amount(value) if isinstance(value, Decimal) else value
                for key, value in preview.items()
            }
            if preview
            else None,
            "current": {
                "original": format_ars_amount(charge.amount),
                "total": format_ars_amount(charge.current_amount),
                "paid": format_ars_amount(charge.paid_amount),
                "balance": format_ars_amount(charge.outstanding),
            },
            "history": [
                {
                    "date": adjustment.created_at,
                    "before": format_ars_amount(adjustment.previous_amount),
                    "after": format_ars_amount(adjustment.resulting_amount),
                    "reason": adjustment.reason,
                    "actor": adjustment.created_by,
                }
                for adjustment in charge.adjustments.select_related("created_by")
            ],
        }
        return TemplateResponse(
            request, "admin/billing/monthlycharge/adjust.html", context
        )

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
