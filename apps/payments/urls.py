from django.urls import path
from .views import CheckoutView, WompiWebhookView, TransactionStatusView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="checkout"),
    path("webhook/", WompiWebhookView.as_view(), name="wompi-webhook"),
    path("transaction/<str:reference>/", TransactionStatusView.as_view(), name="transaction-status"),
]