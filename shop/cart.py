from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError

from .models import Coupon, Product


class Cart:
    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(settings.CART_SESSION_ID, {})

    def save(self):
        self.session.modified = True

    def add(self, product, quantity=1, update=False):
        product_id = str(product.pk)
        current = self.cart.get(product_id, 0)
        quantity = quantity if update else current + quantity
        if quantity < 1:
            raise ValidationError("Количество должно быть больше нуля.")
        if not product.available or quantity > product.stock:
            raise ValidationError(
                f"«{product.name}»: доступно {product.stock} шт."
                if product.available
                else "Товар больше не доступен."
            )
        self.cart[product_id] = quantity
        self.save()

    def remove(self, product_id):
        self.cart.pop(str(product_id), None)
        self.save()

    def __iter__(self):
        # В сессии остаются только числа, объекты моделей туда не записываются.
        products = Product.objects.filter(pk__in=self.cart).select_related("category")
        for product in products:
            quantity = self.cart[str(product.pk)]
            yield {
                "product": product,
                "quantity": quantity,
                "price": product.price,
                "total_price": product.price * quantity,
            }

    def __len__(self):
        return sum(self.cart.values())

    def get_subtotal(self):
        return sum((item["total_price"] for item in self), Decimal("0.00"))

    def get_coupon(self):
        code = self.session.get("coupon_code")
        coupon = Coupon.objects.filter(code=code).first() if code else None
        return coupon if coupon and coupon.is_valid() else None

    def get_discount(self):
        coupon = self.get_coupon()
        return coupon.get_discount(self.get_subtotal()) if coupon else Decimal("0.00")

    def get_total_price(self):
        return self.get_subtotal() - self.get_discount()

    def clear(self):
        self.cart = {}
        self.session.pop(settings.CART_SESSION_ID, None)
        self.session.pop("coupon_code", None)
        self.save()
