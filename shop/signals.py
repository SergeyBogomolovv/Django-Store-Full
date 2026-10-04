from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category, Product


def clear_catalog_cache():
    cache.delete_many(["catalog:products", "catalog:categories"])


@receiver(post_save, sender=Product)
@receiver(post_delete, sender=Product)
@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
def invalidate_catalog(sender, **kwargs):
    transaction.on_commit(clear_catalog_cache)
