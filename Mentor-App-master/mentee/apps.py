# mentee/apps.py
from django.apps import AppConfig

class MenteeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mentee'

    def ready(self):
        import mentee.signals   # 👈 make sure signals are loaded
