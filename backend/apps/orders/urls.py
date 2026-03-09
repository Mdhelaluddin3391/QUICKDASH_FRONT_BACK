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
    path("create/", CreateOrderAPIView.as_view()),
    path("my/", MyOrdersAPIView.as_view()),
    path("<int:id>/", OrderDetailAPIView.as_view()),
    path("<int:order_id>/cancel/", CancelOrderAPIView.as_view()),
    
    path("cart/", CartAPIView.as_view()),
    path("cart/add/", AddToCartAPIView.as_view()),

    path("payment/verify/", RazorpayVerifyAPIView.as_view()),

    path("<int:order_id>/simulate/", OrderSimulationAPIView.as_view()),
    path("validate-cart/", ValidateCartAPIView.as_view(), name="validate-cart"),
]