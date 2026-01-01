from django.urls import path
from .views import SaveLocationAPIView, GeocodeAPIView, MyLocationsListAPIView

urlpatterns = [
    path("save/", SaveLocationAPIView.as_view()),
    path("geocode/", GeocodeAPIView.as_view()),
    path("my/", MyLocationsListAPIView.as_view()),
]