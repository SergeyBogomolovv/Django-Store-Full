from .cart import Cart


def cart_summary(request):
    cart = Cart(request)
    return {
        "cart_count": len(cart),
        "cart_product_ids": {int(product_id) for product_id in cart.cart},
    }
