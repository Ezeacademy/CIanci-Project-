from decimal import Decimal

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from academy.models import Student
from billing.models import MonthlyCharge
from billing.queries import charges_with_economic_totals, students_with_available_credit
from core.money import format_ars_amount

from .models import CreditRelease, Payment, PaymentAllocation, PaymentIntent
from .services import confirm_transfer, register_cash_payment, reject_transfer


def charges_with_balance(student_id):
    return (
        charges_with_economic_totals(
            MonthlyCharge.objects.filter(student_id=student_id)
        )
        .filter(outstanding__gt=0)
        .select_related("student", "discipline")
        .order_by("period", "discipline__name", "pk")
    )


class CashPaymentForm(forms.Form):
    student = forms.ModelChoiceField(
        label=_("Alumno"),
        queryset=Student.objects.order_by("last_name", "first_name", "pk"),
    )
    amount = forms.DecimalField(
        label=_("Importe recibido"),
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        help_text=_(
            "Ingresá pesos enteros o hasta dos decimales con punto, "
            "por ejemplo 30000 o 30000.50."
        ),
    )
    received_at = forms.DateTimeField(
        label=_("Fecha y hora de recepción"),
        initial=timezone.localtime,
        input_formats=("%Y-%m-%dT%H:%M",),
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )
    reference = forms.CharField(
        label=_("Referencia (opcional)"), max_length=255, required=False
    )


class ChargeAllocationForm(forms.Form):
    def __init__(self, *args, student, expected_amount, **kwargs):
        super().__init__(*args, **kwargs)
        self.expected_amount = expected_amount
        self.charges = list(charges_with_balance(student.pk))
        self.balances = {charge.pk: charge.outstanding for charge in self.charges}

        for charge in self.charges:
            self.fields[f"charge_{charge.pk}"] = forms.DecimalField(
                label=_("%(period)s — %(discipline)s")
                % {
                    "period": charge.period.strftime("%m/%Y"),
                    "discipline": charge.discipline.name,
                },
                help_text=_(
                    "Saldo disponible: %(balance)s. Podés ingresar pesos enteros "
                    "o hasta dos decimales con punto."
                )
                % {"balance": format_ars_amount(charge.outstanding)},
                required=False,
                max_digits=12,
                decimal_places=2,
                min_value=Decimal("0.01"),
            )

    def clean(self):
        cleaned_data = super().clean()
        self.assignments = [
            (charge.pk, cleaned_data[f"charge_{charge.pk}"])
            for charge in self.charges
            if cleaned_data.get(f"charge_{charge.pk}") is not None
        ]
        available = sum(self.balances.values(), Decimal("0.00"))
        if self.expected_amount > available:
            raise ValidationError(
                _(
                    "El importe supera la deuda disponible. La operación no se puede "
                    "confirmar ni aplicar parcialmente."
                )
            )
        assigned = sum((amount for _, amount in self.assignments), Decimal("0.00"))
        if assigned != self.expected_amount:
            raise ValidationError(
                _("Las asignaciones deben cubrir exactamente el importe recibido.")
            )
        return cleaned_data


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    fields = ("charge", "formatted_amount")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Importe asignado"), ordering="amount")
    def formatted_amount(self, payment_allocation):
        return format_ars_amount(payment_allocation.amount)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "formatted_amount",
        "currency",
        "method",
        "received_at",
        "confirmed_by",
    )
    list_filter = ("method", "received_at")
    search_fields = ("student__first_name", "student__last_name", "reference")
    readonly_fields = (
        "student",
        "formatted_amount",
        "currency",
        "method",
        "received_at",
        "created_at",
        "confirmed_by",
        "reference",
        "intent",
    )
    fields = readonly_fields
    inlines = (PaymentAllocationInline,)
    change_list_template = "admin/payments/payment/change_list.html"

    def get_urls(self):
        custom_urls = [
            path(
                "cash/add/",
                self.admin_site.admin_view(self.record_cash_view),
                name="payments_payment_record_cash",
            )
        ]
        return custom_urls + super().get_urls()

    @admin.display(description=_("Importe"), ordering="amount")
    def formatted_amount(self, payment):
        return format_ars_amount(payment.amount)

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied
        return HttpResponseRedirect(reverse("admin:payments_payment_record_cash"))

    def record_cash_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        form = CashPaymentForm(request.POST or None)
        allocation_form = None
        if request.method == "POST" and form.is_valid():
            if "_load_charges" in request.POST:
                allocation_form = ChargeAllocationForm(
                    student=form.cleaned_data["student"],
                    expected_amount=form.cleaned_data["amount"],
                )
            elif "_confirm_payment" in request.POST:
                allocation_form = ChargeAllocationForm(
                    request.POST,
                    student=form.cleaned_data["student"],
                    expected_amount=form.cleaned_data["amount"],
                )
                if allocation_form.is_valid():
                    try:
                        payment = register_cash_payment(
                            student_id=form.cleaned_data["student"].pk,
                            amount=form.cleaned_data["amount"],
                            allocations=allocation_form.assignments,
                            received_by=request.user,
                            received_at=form.cleaned_data["received_at"],
                            reference=form.cleaned_data["reference"],
                        )
                    except ValidationError as exc:
                        allocation_form.add_error(None, "; ".join(exc.messages))
                    else:
                        self.log_addition(
                            request, payment, _("Pago en efectivo registrado.")
                        )
                        self.message_user(
                            request,
                            _(
                                "El pago en efectivo se registró y "
                                "asignó correctamente."
                            ),
                            messages.SUCCESS,
                        )
                        return HttpResponseRedirect(
                            reverse("admin:payments_payment_changelist")
                        )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Registrar pago en efectivo"),
            "form": form,
            "allocation_form": allocation_form,
        }
        return TemplateResponse(
            request, "admin/payments/payment/record_cash.html", context
        )

    def has_change_permission(self, request, obj=None):
        return super().has_view_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "formatted_amount",
        "currency",
        "method",
        "status",
        "created_at",
        "created_by",
        "decided_by",
    )
    list_filter = ("status", "method", "created_at")
    search_fields = ("student__first_name", "student__last_name", "reference")
    autocomplete_fields = ("student",)
    fields = (
        "student",
        "method",
        "amount",
        "currency",
        "reference",
        "status",
        "created_at",
        "created_by",
        "decided_at",
        "decided_by",
    )
    change_form_template = "admin/payments/paymentintent/change_form.html"
    actions = ("reject_selected_transfers",)

    def get_urls(self):
        custom_urls = [
            path(
                "<path:object_id>/confirm/",
                self.admin_site.admin_view(self.confirm_transfer_view),
                name="payments_paymentintent_confirm",
            )
        ]
        return custom_urls + super().get_urls()

    def get_fields(self, request, obj=None):
        if obj is None:
            return ("student", "amount", "reference")
        return tuple(
            "formatted_amount" if field_name == "amount" else field_name
            for field_name in self.fields
        )

    def get_form(self, request, obj=None, **kwargs):
        payment_intent_form = super().get_form(request, obj, **kwargs)
        if obj is None and "amount" in payment_intent_form.base_fields:
            payment_intent_form.base_fields["amount"].help_text = _(
                "Ingresá pesos enteros o hasta dos decimales con punto, "
                "por ejemplo 30000 o 30000.50."
            )
        return payment_intent_form

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.get_fields(request, obj)
        return ()

    @admin.display(description=_("Importe"), ordering="amount")
    def formatted_amount(self, payment_intent):
        return format_ars_amount(payment_intent.amount)

    def save_model(self, request, obj, form, change):
        if change:
            raise PermissionDenied
        from .services import register_transfer_intent

        saved = register_transfer_intent(
            student_id=obj.student_id,
            amount=obj.amount,
            created_by=request.user,
            reference=obj.reference,
        )
        obj.pk = saved.pk
        obj._state.adding = False
        obj._state.db = saved._state.db
        obj.created_by = saved.created_by
        obj.created_at = saved.created_at

    def confirm_transfer_view(self, request, object_id):
        intent = self.get_object(request, object_id)
        if intent is None:
            raise PermissionDenied
        if not self.has_change_permission(request, intent):
            raise PermissionDenied

        if intent.status != PaymentIntent.Status.PENDING:
            self.message_user(
                request, _("La transferencia ya fue resuelta."), messages.INFO
            )
            return HttpResponseRedirect(
                reverse("admin:payments_paymentintent_change", args=(intent.pk,))
            )

        form = ChargeAllocationForm(
            request.POST or None,
            student=intent.student,
            expected_amount=intent.amount,
        )
        if request.method == "POST" and form.is_valid():
            try:
                payment = confirm_transfer(
                    intent_id=intent.pk,
                    allocations=form.assignments,
                    confirmed_by=request.user,
                )
            except ValidationError as exc:
                form.add_error(None, "; ".join(exc.messages))
            else:
                self.log_change(
                    request,
                    intent,
                    _("Transferencia confirmada y asignada al pago %(payment)s.")
                    % {"payment": payment.pk},
                )
                self.message_user(
                    request,
                    _("La transferencia se confirmó y asignó correctamente."),
                    messages.SUCCESS,
                )
                return HttpResponseRedirect(
                    reverse("admin:payments_paymentintent_change", args=(intent.pk,))
                )

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": intent,
            "formatted_amount": format_ars_amount(intent.amount),
            "title": _("Confirmar y asignar transferencia"),
            "form": form,
        }
        return TemplateResponse(
            request, "admin/payments/paymentintent/confirm.html", context
        )

    @admin.action(
        description=_("Rechazar transferencias seleccionadas"),
        permissions=("change",),
    )
    def reject_selected_transfers(self, request, queryset):
        rejected = 0
        skipped = 0
        for intent in queryset.filter(status=PaymentIntent.Status.PENDING):
            try:
                reject_transfer(intent_id=intent.pk, rejected_by=request.user)
            except ValidationError:
                skipped += 1
                continue
            self.log_change(request, intent, _("Transferencia rechazada."))
            rejected += 1
        self.message_user(
            request,
            _(
                "Se rechazaron %(rejected)s transferencias pendientes. "
                "No se pudieron resolver %(skipped)s."
            )
            % {"rejected": rejected, "skipped": skipped},
            messages.WARNING if skipped else messages.SUCCESS,
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditRelease)
class CreditReleaseAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "released_amount",
        "available_credit",
        "payment",
        "allocation",
        "adjustment",
        "created_at",
    )
    readonly_fields = (
        "student",
        "released_amount",
        "available_credit",
        "payment",
        "allocation",
        "adjustment",
        "created_at",
    )
    fields = readonly_fields
    search_fields = (
        "allocation__payment__student__first_name",
        "allocation__payment__student__last_name",
    )
    list_filter = ("created_at",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "allocation__payment__student",
                "allocation__charge__discipline",
                "allocation__charge__student",
                "adjustment__charge__student",
                "adjustment__charge__discipline",
            )
        )

    @admin.display(description=_("Alumno"))
    def student(self, release):
        return release.allocation.payment.student

    @admin.display(description=_("Pago de origen"))
    def payment(self, release):
        from django.utils.html import format_html

        payment = release.allocation.payment
        return format_html(
            '<a href="{}">Pago #{} — {} — {}</a>',
            reverse("admin:payments_payment_change", args=(payment.pk,)),
            payment.pk,
            payment.get_method_display(),
            format_ars_amount(payment.amount),
        )

    @admin.display(description=_("Crédito generado"))
    def released_amount(self, release):
        return format_ars_amount(release.amount)

    @admin.display(description=_("Saldo disponible del alumno"))
    def available_credit(self, release):
        student = students_with_available_credit(
            Student.objects.filter(pk=release.allocation.payment.student_id)
        ).get()
        return format_ars_amount(student.available_credit)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
