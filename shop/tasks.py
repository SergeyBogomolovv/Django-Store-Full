from celery import shared_task
from django.core.mail import send_mail

from .models import Order


@shared_task
def order_confirmation(order_id):
    order = Order.objects.prefetch_related("items").get(pk=order_id)
    items = "\n".join(
        f"{item.product_name} × {item.quantity}: {item.get_cost()} ₽"
        for item in order.items.all()
    )
    send_mail(
        f"Полка: заказ №{order.pk}",
        f"Спасибо за заказ!\n\n{items}\n\n"
        f"Итого: {order.get_total_cost()} ₽.\n"
        f"Доставка: {order.delivery_date:%d.%m.%Y}.\n"
        f"Оплата: {order.get_payment_method_display()}.",
        None,
        [order.email],
    )
