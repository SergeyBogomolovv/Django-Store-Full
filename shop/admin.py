from django.contrib import admin
from django.utils import timezone

from .models import Category, Coupon, Order, OrderItem, Product, Review, Wishlist


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "price", "stock", "available", "created", "updated"]
    list_filter = ["available", "category", "created", "updated"]
    list_editable = ["price", "stock", "available"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "author", "description"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    raw_id_fields = ["product"]
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    change_list_template = "admin/shop/order/change_list.html"
    list_display = [
        "id",
        "first_name",
        "last_name",
        "email",
        "paid",
        "status",
        "created",
        "updated",
    ]
    list_filter = ["paid", "status", "created", "updated"]
    search_fields = ["first_name", "last_name", "email", "address"]
    readonly_fields = ["created", "updated"]
    inlines = [OrderItemInline]
    actions = ["mark_paid", "mark_shipped", "mark_completed"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("items")

    @admin.action(description="Отметить как оплаченные")
    def mark_paid(self, request, queryset):
        count = queryset.update(paid=True, updated=timezone.now())
        self.message_user(request, f"Оплачено заказов: {count}.")

    @admin.action(description="Перевести в статус «Отправлен»")
    def mark_shipped(self, request, queryset):
        count = queryset.update(status=Order.Status.SHIPPED, updated=timezone.now())
        self.message_user(request, f"Отправлено заказов: {count}.")

    @admin.action(description="Перевести в статус «Завершено»")
    def mark_completed(self, request, queryset):
        count = queryset.update(status=Order.Status.COMPLETED, updated=timezone.now())
        self.message_user(request, f"Завершено заказов: {count}.")


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ["code", "kind", "value", "active", "valid_from", "valid_to"]
    list_filter = ["active", "kind"]
    search_fields = ["code"]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "created_at"]
    list_filter = ["rating", "created_at"]
    search_fields = ["product__name", "comment"]
    readonly_fields = ["created_at"]


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "created"]
