from django.urls import path

from . import views

app_name = "shop"
urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("health/", views.health, name="health"),
    path(
        "category/<slug:category_slug>/",
        views.product_list,
        name="product_list_by_category",
    ),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.cart_add, name="cart_add"),
    path("cart/remove/<int:product_id>/", views.cart_remove, name="cart_remove"),
    path("cart/coupon/", views.coupon_apply, name="coupon_apply"),
    path("cart/coupon/remove/", views.coupon_remove, name="coupon_remove"),
    path("orders/create/", views.order_create, name="order_create"),
    path("orders/<int:order_id>/created/", views.order_created, name="order_created"),
    path("reviews/<int:product_id>/", views.review_add, name="review_add"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/<int:product_id>/", views.wishlist_toggle, name="wishlist_toggle"),
]
