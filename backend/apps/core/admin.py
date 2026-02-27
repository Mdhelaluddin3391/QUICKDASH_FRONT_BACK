import csv
from django.http import HttpResponse
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import StoreSettings


def export_as_csv(modeladmin, request, queryset):
    """
    Yeh function selected rows ko CSV format mein export karega.
    """
    meta = modeladmin.model._meta
    field_names = [field.name for field in meta.fields]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename={meta.model_name}_export.csv'
    
    writer = csv.writer(response)
    writer.writerow(field_names)
    
    for obj in queryset:
        row = []
        for field in field_names:
            value = getattr(obj, field)
            if callable(value):
                try:
                    value = value()
                except Exception:
                    value = str(value)
            row.append(str(value))
        writer.writerow(row)
        
    return response

export_as_csv.short_description = "Export Selected to CSV"

admin.site.add_action(export_as_csv, "export_as_csv")

@admin.register(StoreSettings)
class StoreSettingsAdmin(ImportExportModelAdmin):
    list_display = ['is_store_open', 'store_closed_message']
    
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)