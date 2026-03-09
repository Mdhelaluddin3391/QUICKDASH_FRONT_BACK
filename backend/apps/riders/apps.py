from django.apps import AppConfig

class RidersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.riders"

    def ready(self):
        # Ye line bahut zaroori hai, iske bina Rider Online signal kaam nahi karega
        import apps.riders.signals