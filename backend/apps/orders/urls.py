# apps/orders/urls.py
from django.urls import path
from .views import (
    CreateOrderAPIView, 
    MyOrdersAPIView, 
    OrderDetailAPIView,
    CancelOrderAPIView, 
    CartAPIView, 
    AddToCartAPIView,
    OrderSimulationAPIView
)
from apps.payments.views import RazorpayVerifyAPIView
from .views import ValidateCartAPIView


urlpatterns = [
    # Order Lifecycle
    path("create/", CreateOrderAPIView.as_view()),
    path("my/", MyOrdersAPIView.as_view()),
    path("<int:id>/", OrderDetailAPIView.as_view()),
    path("<int:order_id>/cancel/", CancelOrderAPIView.as_view()),
    
    # Cart Management
    path("cart/", CartAPIView.as_view()),
    path("cart/add/", AddToCartAPIView.as_view()),

    # Payment Proxy
    path("payment/verify/", RazorpayVerifyAPIView.as_view()),

    # Operational Override (Admin Only)
    path("<int:order_id>/simulate/", OrderSimulationAPIView.as_view()),
    path("validate-cart/", ValidateCartAPIView.as_view(), name="validate-cart"),
]