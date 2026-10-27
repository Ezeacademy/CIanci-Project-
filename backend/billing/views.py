from decimal import Decimal

from django.db.models import Sum
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from academy.queries import accessible_students

from .models import MonthlyCharge
from .queries import charges_with_economic_totals, students_with_available_credit
from .serializers import FinancialStudentSerializer, MonthlyChargeReadSerializer


class FinancialPageNumberPagination(PageNumberPagination):
    page_size = 50


class MyMonthlyChargesView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = FinancialPageNumberPagination
    serializer_class = MonthlyChargeReadSerializer

    def get_queryset(self):
        return (
            charges_with_economic_totals(
                MonthlyCharge.objects.filter(
                    student__in=accessible_students(self.request.user)
                )
            )
            .select_related("student", "discipline")
            .prefetch_related("adjustments")
            .order_by("-period", "student__last_name", "student__first_name", "pk")
        )

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        totals = queryset.aggregate(
            amount=Sum("current_amount"), paid=Sum("paid_amount")
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
        response.data["credits"] = [
            {
                "student": FinancialStudentSerializer(
                    student, context={"request": request}
                ).data,
                "availableAmount": format(student.available_credit, ".2f"),
            }
            for student in students_with_available_credit(
                accessible_students(request.user)
            )
        ]
        response["Cache-Control"] = "no-store"
        return response

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response
