from django.apps import AppConfig


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"
    verbose_name = "Магазин"

    def ready(self):
        from . import signals  # noqa: F401
