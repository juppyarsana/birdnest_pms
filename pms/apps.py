from django.apps import AppConfig


class PmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'pms'
    
    def ready(self):
        import pms.signals
