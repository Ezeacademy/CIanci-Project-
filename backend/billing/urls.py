from django.urls import path

from .admin_api import AdminMonthlyChargeDetailView, AdminMonthlyChargeListView
from .views import MyMonthlyChargesView

urlpatterns = [
    path(
        "admin/billing/monthly-charges",
        AdminMonthlyChargeListView.as_view(),
        name="admin-billing-monthly-charges",
    ),
    path(
        "admin/billing/monthly-charges/<int:charge_id>",
        AdminMonthlyChargeDetailView.as_view(),
        name="admin-billing-monthly-charge-detail",
    ),
    path(
        "billing/me/charges",
        MyMonthlyChargesView.as_view(),
        name="billing-my-charges",
    ),
]
