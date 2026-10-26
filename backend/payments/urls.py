from django.urls import path

from .views import MyConfirmedPaymentsView, MyPaymentIntentsView

urlpatterns = [
    path(
        "payments/me/confirmed",
        MyConfirmedPaymentsView.as_view(),
        name="payments-my-confirmed",
    ),
    path(
        "payments/me/intents",
        MyPaymentIntentsView.as_view(),
        name="payments-my-intents",
    ),
]
