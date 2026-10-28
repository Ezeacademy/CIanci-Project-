from decimal import Decimal

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from academy.models import Discipline
from adminpanel.permissions import has_admin_permission
from payments.models import PaymentAllocation

from .models import ChargeAdjustment, MonthlyCharge
from .queries import charges_with_economic_totals, sum_charge_economic_totals

MONTHLY_CHARGE_READ_PERMISSIONS = (
    "billing.view_monthlycharge",
    "billing.view_chargeadjustment",
    "payments.view_payment",
)

CHARGE_STATUSES = (
    ("all", "Todas"),
    ("pending", "Pendiente"),
    ("paid", "Pagada"),
    ("scholarship", "Cubierta por beca"),
    ("adjusted_to_zero", "Anulada"),
)


class MonthlyChargeFiltersSerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    period = serializers.RegexField(
        r"^\d{4}-(0[1-9]|1[0-2])$", required=False, max_length=7
    )
    discipline = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        choices=tuple((value, value) for value, _label in CHARGE_STATUSES),
        required=False,
        default="all",
    )


class MonthlyChargePagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminBillingAPIView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response

    def require_read_permissions(self):
        if not all(
            has_admin_permission(self.request.user, permission)
            for permission in MONTHLY_CHARGE_READ_PERMISSIONS
        ):
            raise PermissionDenied("No tenés permiso para consultar mensualidades.")


class AdminMonthlyChargeListView(AdminBillingAPIView):
    def get(self, request):
        self.require_read_permissions()
        filters = MonthlyChargeFiltersSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        values = filters.validated_data

        charges = charges_with_economic_totals(
            MonthlyCharge.objects.select_related("student", "discipline")
        )

        search = values.get("q", "").strip()
        for word in search.split()[:5]:
            charges = charges.filter(
                Q(student__first_name__icontains=word)
                | Q(student__last_name__icontains=word)
            )
        if period := values.get("period"):
            charges = charges.filter(
                period__year=int(period[:4]), period__month=int(period[5:])
            )
        if discipline_id := values.get("discipline"):
            charges = charges.filter(discipline_id=discipline_id)
        charges = filter_charge_status(charges, values.get("status", "all"))
        charges = charges.order_by(
            "-period", "student__last_name", "student__first_name", "pk"
        )

        totals = sum_charge_economic_totals(charges)
        charges = charges.annotate(
            has_adjustments=Exists(
                ChargeAdjustment.objects.filter(charge_id=OuterRef("pk"))
            )
        )
        charges = charges.order_by(
            "-period", "student__last_name", "student__first_name", "pk"
        )
        paginator = MonthlyChargePagination()
        page = paginator.paginate_queryset(charges, request, view=self)
        response = paginator.get_paginated_response(
            [serialize_charge_summary(charge) for charge in page]
        )
        response.data["pageSize"] = paginator.get_page_size(request)
        response.data["summary"] = {
            "currentAmount": format_money(totals["current_amount"]),
            "paidAmount": format_money(totals["paid_amount"]),
            "outstanding": format_money(totals["outstanding"]),
        }
        response.data["filters"] = {
            "periods": [
                period.strftime("%Y-%m")
                for period in MonthlyCharge.objects.order_by()
                .values_list("period", flat=True)
                .distinct()
                .order_by("-period")
            ],
            "disciplines": list(
                Discipline.objects.filter(monthly_charges__isnull=False)
                .order_by("name", "pk")
                .values("id", "name")
                .distinct()
            ),
            "statuses": [
                {"value": value, "label": label} for value, label in CHARGE_STATUSES
            ],
        }
        return response


class AdminMonthlyChargeDetailView(AdminBillingAPIView):
    def get(self, request, charge_id):
        self.require_read_permissions()
        adjustment_queryset = ChargeAdjustment.objects.select_related(
            "created_by"
        ).order_by("created_at", "pk")
        allocation_queryset = (
            PaymentAllocation.objects.select_related("payment", "payment__confirmed_by")
            .prefetch_related("credit_releases")
            .order_by("payment__received_at", "pk")
        )
        charge = get_object_or_404(
            charges_with_economic_totals(
                MonthlyCharge.objects.select_related(
                    "student", "discipline", "price_applied"
                ).prefetch_related(
                    Prefetch("adjustments", queryset=adjustment_queryset),
                    Prefetch("payment_allocations", queryset=allocation_queryset),
                )
            ).annotate(
                has_adjustments=Exists(
                    ChargeAdjustment.objects.filter(charge_id=OuterRef("pk"))
                )
            ),
            pk=charge_id,
        )

        adjustments = [
            {
                "id": adjustment.pk,
                "previousAmount": format_money(adjustment.previous_amount),
                "resultingAmount": format_money(adjustment.resulting_amount),
                "difference": format_money(adjustment.difference),
                "reason": adjustment.reason,
                "createdAt": adjustment.created_at.isoformat(),
                "responsible": display_name(adjustment.created_by),
                "isReversal": adjustment.reverses_id is not None,
            }
            for adjustment in charge.adjustments.all()
        ]
        payments = []
        for allocation in charge.payment_allocations.all():
            released_amount = sum(
                (release.amount for release in allocation.credit_releases.all()),
                Decimal("0.00"),
            )
            payments.append(
                {
                    "id": allocation.pk,
                    "receivedAt": allocation.payment.received_at.isoformat(),
                    "method": allocation.payment.get_method_display(),
                    "allocatedAmount": format_money(allocation.amount),
                    "releasedAmount": format_money(released_amount),
                    "appliedAmount": format_money(allocation.amount - released_amount),
                    "responsible": display_name(allocation.payment.confirmed_by),
                }
            )

        return Response(
            {
                **serialize_charge_summary(charge),
                "studentId": charge.student_id,
                "createdAt": charge.created_at.isoformat(),
                "scholarshipPercentage": charge.scholarship_percentage,
                "adjustments": adjustments,
                "payments": payments,
            }
        )


def filter_charge_status(charges, status):
    if status == "pending":
        return charges.filter(current_amount__gt=0, outstanding__gt=0)
    if status == "paid":
        return charges.filter(current_amount__gt=0, outstanding=0)
    if status == "scholarship":
        return charges.filter(current_amount=0).filter(
            ~Exists(ChargeAdjustment.objects.filter(charge_id=OuterRef("pk")))
        )
    if status == "adjusted_to_zero":
        return charges.filter(current_amount=0).filter(
            Exists(ChargeAdjustment.objects.filter(charge_id=OuterRef("pk")))
        )
    return charges


def serialize_charge_summary(charge):
    if charge.current_amount == 0:
        status = "adjusted_to_zero" if charge.has_adjustments else "scholarship"
    else:
        status = "paid" if charge.outstanding == 0 else "pending"

    return {
        "id": charge.pk,
        "studentId": charge.student_id,
        "studentName": str(charge.student),
        "discipline": charge.discipline.name,
        "period": charge.period.strftime("%Y-%m"),
        "baseAmount": format_money(charge.base_amount),
        "discountAmount": format_money(charge.discount_amount),
        "originalAmount": format_money(charge.amount),
        "adjustmentAmount": format_money(charge.adjustment_amount),
        "currentAmount": format_money(charge.current_amount),
        "paidAmount": format_money(charge.paid_amount),
        "outstanding": format_money(charge.outstanding),
        "status": status,
    }


def format_money(value):
    return format(value or Decimal("0.00"), ".2f")


def display_name(user):
    return (user.get_full_name() or "").strip() or "Personal autorizado"
