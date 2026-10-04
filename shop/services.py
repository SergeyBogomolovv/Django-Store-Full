import logging
from functools import partial

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Coupon, OrderItem, Product
from .tasks import order_confirmation

logger = logging.getLogger(__name__)


def queue_order_confirmation(order_id):
    try:
        order_confirmation.delay(order_id)
    except Exception:
        # Сбой очереди писем не должен превращать уже созданный заказ в ошибку.
        logger.exception("Не удалось отправить уведомление о заказе %s", order_id)


@transaction.atomic
def create_order(cart, form, user):
    if not cart.cart:
        raise ValidationError("Корзина пуста.")

    # Блокируем остатки до конца транзакции: последнюю книгу купит один клиент.
    products = list(
        Product.objects.select_for_update().filter(pk__in=cart.cart).order_by("pk")
    )
    if len(products) != len(cart.cart):
        raise ValidationError("Некоторые товары удалены. Обновите корзину.")

    subtotal = 0
    for product in products:
        quantity = cart.cart[str(product.pk)]
        if not product.available or quantity > product.stock:
            raise ValidationError(
                f"«{product.name}»: товар недоступен или осталось {product.stock} шт."
            )
        subtotal += product.price * quantity

    coupon = None
    code = cart.session.get("coupon_code")
    if code:
        coupon = Coupon.objects.select_for_update().filter(code=code).first()
        if not coupon or not coupon.is_valid():
            raise ValidationError("Промокод истёк. Удалите его или примените другой.")

    order = form.save(commit=False)
    if user.is_authenticated:
        order.user = user
    if coupon:
        order.coupon_code = coupon.code
        order.discount = coupon.get_discount(subtotal)
    order.save()

    for product in products:
        quantity = cart.cart[str(product.pk)]
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            price=product.price,
            quantity=quantity,
        )
        product.stock -= quantity
        product.save(update_fields=["stock", "updated"])

    transaction.on_commit(partial(queue_order_confirmation, order.pk))
    return order
