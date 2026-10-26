from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from academy.queries import accessible_students

from .models import Payment, PaymentIntent
from .serializers import PaymentIntentReadSerializer, PaymentReadSerializer


class FinancialPageNumberPagination(PageNumberPagination):
    page_size = 50


class PrivateFinancialListView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = FinancialPageNumberPagination

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class MyConfirmedPaymentsView(PrivateFinancialListView):
    serializer_class = PaymentReadSerializer

    def get_queryset(self):
        return (
            Payment.objects.filter(student__in=accessible_students(self.request.user))
            .select_related("student")
            .prefetch_related("allocations__charge__discipline")
        )


class MyPaymentIntentsView(PrivateFinancialListView):
    serializer_class = PaymentIntentReadSerializer

    def get_queryset(self):
        return PaymentIntent.objects.filter(
            student__in=accessible_students(self.request.user),
            status__in=(PaymentIntent.Status.PENDING, PaymentIntent.Status.REJECTED),
        ).select_related("student").order_by("-created_at", "-pk")
