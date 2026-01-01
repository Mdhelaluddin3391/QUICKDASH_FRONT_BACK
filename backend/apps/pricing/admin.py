# apps/pricing/admin.py
from django.contrib import admin
from .models import SurgeRule

@admin.register(SurgeRule)
class SurgeRuleAdmin(admin.ModelAdmin):
    list_display = ("warehouse", "max_multiplier", "base_factor")
    autocomplete_fields = ["warehouse"]