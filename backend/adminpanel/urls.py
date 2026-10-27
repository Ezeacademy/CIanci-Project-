from django.urls import path

from .views import AdminDashboardView

urlpatterns = [
    path("admin-panel/dashboard", AdminDashboardView.as_view(), name="admin-dashboard"),
]
