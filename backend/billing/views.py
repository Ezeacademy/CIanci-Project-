from decimal import Decimal

from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from academy.queries import accessible_students
from payments.models import PaymentAllocation

from .models import MonthlyCharge
from .serializers import MonthlyChargeReadSerializer


class FinancialPageNumberPagination(PageNumberPagination):
    page_size = 50


class MyMonthlyChargesView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = FinancialPageNumberPagination
    serializer_class = MonthlyChargeReadSerializer

    def get_queryset(self):
        paid_amount = (
            PaymentAllocation.objects.filter(charge_id=OuterRef("pk"))
            .values("charge_id")
            .annotate(total=Sum("amount"))
            .values("total")
        )
        zero = Value(
            Decimal("0.00"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
        return (
            MonthlyCharge.objects.filter(
                student__in=accessible_students(self.request.user)
            )
            .select_related("student", "discipline")
            .annotate(paid_amount=Coalesce(Subquery(paid_amount), zero))
            .order_by("-period", "student__last_name", "student__first_name", "pk")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        totals = queryset.aggregate(
            amount=Sum("amount"), paid=Sum("paid_amount")
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data["summary"] = {
            "amount": format(totals["amount"] or Decimal("0.00"), ".2f"),
            "paidAmount": format(totals["paid"] or Decimal("0.00"), ".2f"),
            "balance": format(
                (totals["amount"] or Decimal("0.00"))
                - (totals["paid"] or Decimal("0.00")),
                ".2f",
            ),
        }
        response["Cache-Control"] = "no-store"
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
