from django.urls import path
from .views import SurgeRuleListCreateAPIView, SurgeRuleDetailAPIView

urlpatterns = [
    path("rules/", SurgeRuleListCreateAPIView.as_view()),
    path("rules/<int:pk>/", SurgeRuleDetailAPIView.as_view()),
]