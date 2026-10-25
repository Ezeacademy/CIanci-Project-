from django.urls import path

from .views import AccessibleStudentListView, StudentEnrollmentListView

urlpatterns = [
    path(
        "academic/me/students",
        AccessibleStudentListView.as_view(),
        name="academic-my-students",
    ),
    path(
        "academic/students/<int:student_id>/enrollments",
        StudentEnrollmentListView.as_view(),
        name="academic-student-enrollments",
    ),
]
