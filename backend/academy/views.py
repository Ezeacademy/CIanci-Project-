from django.db.models import F
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from .models import Enrollment
from .queries import accessible_students
from .serializers import AccessibleStudentSerializer, EnrollmentSerializer


class AcademicPageNumberPagination(PageNumberPagination):
    page_size = 50


class AcademicReadOnlyListView(generics.ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = AcademicPageNumberPagination

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        return response


class AccessibleStudentListView(AcademicReadOnlyListView):
    serializer_class = AccessibleStudentSerializer

    def get_queryset(self):
        return accessible_students(self.request.user)


class StudentEnrollmentListView(AcademicReadOnlyListView):
    serializer_class = EnrollmentSerializer
    valid_statuses = {"active", "history", "all"}

    def get_queryset(self):
        student = get_object_or_404(
            accessible_students(self.request.user), pk=self.kwargs["student_id"]
        )
        status = self.request.query_params.get("status", "active")
        if status not in self.valid_statuses:
            raise ValidationError({"status": "Debe ser active, history o all."})

        enrollments = Enrollment.objects.filter(student=student).select_related(
            "discipline"
        )
        if status == "active":
            return enrollments.filter(ended_at__isnull=True)
        if status == "history":
            return enrollments.filter(ended_at__isnull=False)
        return enrollments.order_by(
            F("ended_at").asc(nulls_first=True), "-enrolled_at", "-pk"
        )
