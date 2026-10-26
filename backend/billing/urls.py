from django.urls import path

from .views import MyMonthlyChargesView

urlpatterns = [
    path(
        "billing/me/charges",
        MyMonthlyChargesView.as_view(),
        name="billing-my-charges",
    ),
]
