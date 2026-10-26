from decimal import Decimal

from django.contrib import admin
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils.translation import gettext_lazy as _

from .models import DisciplinePrice, MonthlyCharge


@admin.register(DisciplinePrice)
class DisciplinePriceAdmin(admin.ModelAdmin):
    list_display = (
        "discipline",
        "amount",
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
                ("discipline", "amount", "currency", "effective_month")
            )
        return tuple(readonly_fields)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MonthlyCharge)
class MonthlyChargeAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "discipline",
        "period",
        "amount",
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
        "price_applied",
        "amount",
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
    def paid_amount(self, obj):
        return obj.applied_amount

    @admin.display(description=_("Saldo pendiente"))
    def outstanding_balance(self, obj):
        return obj.amount - obj.applied_amount

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)
