from django.urls import path

from .views import (
    AccessibleStudentListView,
    MyClassCalendarView,
    StudentEnrollmentListView,
)

urlpatterns = [
    path(
        "academic/me/calendar",
        MyClassCalendarView.as_view(),
        name="academic-my-calendar",
    ),
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
