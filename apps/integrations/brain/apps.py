from django.apps import AppConfig

class IntegrationConfig(AppConfig):
    name = 'apps.integrations.brain'
    verbose_name = "Brain API"
    default_auto_field = 'django.db.models.BigAutoField'
