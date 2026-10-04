from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from .cart import Cart
from .forms import OrderCreateForm
from .models import Category, Coupon, Order, OrderItem, Product, Review, Wishlist
from .services import create_order
from .tasks import order_confirmation

User = get_user_model()
TEST_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def order_data(**changes):
    return {
        "first_name": "Иван",
        "last_name": "Иванов",
        "email": "reader@example.com",
        "phone": "8(999)123-45-67",
        "address": "Книжная, 1",
        "postal_code": "123456",
        "city": "Москва",
        "delivery_method": "courier",
        "delivery_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
        "payment_method": "on_receipt",
        **changes,
    }


@override_settings(CACHES=TEST_CACHE, CELERY_TASK_ALWAYS_EAGER=True)
class ShopTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name="Научпоп", slug="science")
        cls.product = Product.objects.create(
            category=cls.category,
            name="Космос",
            slug="cosmos",
            description="Путешествие среди звёзд",
            price="500.00",
            stock=3,
        )
        cls.user = User.objects.create_user(
            username="reader123",
            password="testpass123",
            full_name="Иванов Иван",
            phone="8(999)123-45-67",
            email="reader@example.com",
        )
        cls.other_user = User.objects.create_user(
            username="another123",
            password="testpass123",
            email="other@example.com",
        )

    def setUp(self):
        cache.clear()

    def add_to_cart(self, product=None, quantity=1, **kwargs):
        return self.client.post(
            reverse("shop:cart_add", args=[(product or self.product).pk]),
            {"quantity": quantity, **kwargs},
        )

    def place_order(self, **changes):
        return self.client.post(reverse("shop:order_create"), order_data(**changes))

    def create_coupon(self, **changes):
        return Coupon.objects.create(
            **{
                "code": "POLKA10",
                "kind": "percent",
                "value": 10,
                "valid_to": timezone.now() + timedelta(days=1),
                **changes,
            }
        )

    def test_catalog_search_category_price_and_sort(self):
        second = Product.objects.create(
            category=self.category,
            name="Физика",
            slug="physics",
            price=900,
            stock=5,
        )
        response = self.client.get(
            "/", {"q": "звёзд", "min_price": 400, "max_price": 600}
        )
        self.assertContains(response, "Космос")
        self.assertNotContains(response, "Физика")
        response = self.client.get(self.category.get_absolute_url(), {"sort": "-price"})
        self.assertEqual(list(response.context["page_obj"]), [second, self.product])

    def test_invalid_filters_do_not_crash(self):
        for params in [
            {"min_price": "NaN"},
            {"min_price": "text"},
            {"sort": "invalid"},
            {"min_price": 900, "max_price": 100},
        ]:
            with self.subTest(params=params):
                response = self.client.get("/", params)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["filter_form"].errors)

    def test_cyrillic_search_is_case_insensitive(self):
        for query in ["космос", "КОСМОС", "ЗВЁЗД"]:
            with self.subTest(query=query):
                response = self.client.get("/", {"q": query})
                self.assertEqual(list(response.context["page_obj"]), [self.product])

    def test_cart_update_and_remove(self):
        self.add_to_cart(quantity=2)
        self.add_to_cart(quantity=1, update=True)
        self.assertEqual(self.client.session["cart"], {str(self.product.pk): 1})
        response = self.client.get(reverse("shop:cart_detail"))
        self.assertContains(response, "500,00 ₽")
        self.client.post(reverse("shop:cart_remove", args=[self.product.pk]))
        self.assertEqual(self.client.session["cart"], {})

    def test_quantity_and_stock_limits(self):
        for quantity in [0, -1, 4, "1.5", "abc"]:
            with self.subTest(quantity=quantity):
                self.add_to_cart(quantity=quantity)
                self.assertFalse(self.client.session.get("cart"))
        self.add_to_cart(quantity=2)
        self.add_to_cart(quantity=2)
        self.assertEqual(self.client.session["cart"][str(self.product.pk)], 2)

    def test_cart_json_response(self):
        response = self.client.post(
            reverse("shop:cart_add", args=[self.product.pk]),
            {"quantity": 2},
            HTTP_ACCEPT="application/json",
        )
        self.assertEqual(response.json()["cart_count"], 2)
        self.assertEqual(response.status_code, 200)

    def test_mutations_require_post_and_csrf(self):
        for name in ["cart_add", "cart_remove"]:
            url = reverse(f"shop:{name}", args=[self.product.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            self.assertEqual(
                Client(enforce_csrf_checks=True).post(url, {"quantity": 1}).status_code,
                403,
            )

    def test_checkout_saves_items_stock_user_and_frozen_prices(self):
        self.client.force_login(self.user)
        self.add_to_cart(quantity=2)
        with patch("shop.services.order_confirmation.delay") as send:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.place_order()
        order = Order.objects.get()
        self.assertRedirects(response, reverse("shop:order_created", args=[order.pk]))
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.items.get().quantity, 2)
        self.assertEqual(order.get_total_cost(), Decimal("1000.00"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertNotIn("cart", self.client.session)
        send.assert_called_once_with(order.pk)
        self.product.price = Decimal("700.00")
        self.product.save()
        self.assertEqual(order.get_total_cost(), Decimal("1000.00"))

    def test_checkout_uses_current_price(self):
        self.add_to_cart()
        Product.objects.filter(pk=self.product.pk).update(price=600)
        self.place_order()
        self.assertEqual(Order.objects.get().get_total_cost(), Decimal("600.00"))

    def test_stock_change_rolls_back_entire_order_and_keeps_cart(self):
        second = Product.objects.create(
            category=self.category,
            name="Вторая",
            slug="second",
            price=300,
            stock=2,
        )
        self.add_to_cart()
        self.add_to_cart(product=second, quantity=2)
        Product.objects.filter(pk=second.pk).update(stock=1)
        response = self.place_order()
        self.assertContains(response, "осталось 1")
        self.assertFalse(Order.objects.exists())
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(len(self.client.session["cart"]), 2)

    def test_empty_checkout_and_repeated_submission_do_not_create_orders(self):
        self.place_order()
        self.assertFalse(Order.objects.exists())
        self.add_to_cart()
        self.place_order()
        self.place_order()
        self.assertEqual(Order.objects.count(), 1)

    def test_delivery_validation_and_sbp_selection(self):
        form = OrderCreateForm(
            order_data(
                delivery_date=(timezone.localdate() - timedelta(days=1)).isoformat(),
                postal_code="",
                address="",
            )
        )
        self.assertFalse(form.is_valid())
        self.assertIn("delivery_date", form.errors)
        self.assertIn("address", form.errors)
        self.assertIn("postal_code", form.errors)
        self.add_to_cart()
        self.place_order(
            delivery_method="pickup",
            payment_method="sbp",
            address="",
            postal_code="",
            city="",
        )
        order = Order.objects.get()
        self.assertEqual(order.payment_method, "sbp")
        self.assertFalse(order.paid)

    def test_percent_coupon_and_fixed_discount_cap(self):
        self.create_coupon()
        self.add_to_cart(quantity=2)
        self.client.post(reverse("shop:coupon_apply"), {"code": "polka10"})
        self.place_order()
        order = Order.objects.get()
        self.assertEqual(order.discount, Decimal("100.00"))
        self.assertEqual(order.get_total_cost(), Decimal("900.00"))
        self.assertEqual(order.coupon_code, "POLKA10")
        self.assertNotIn("coupon_code", self.client.session)
        fixed = self.create_coupon(code="BOOK200", kind="fixed", value=200)
        self.assertEqual(fixed.get_discount(Decimal("100")), Decimal("100.00"))

    def test_expired_coupon_blocks_checkout_until_removed(self):
        coupon = self.create_coupon()
        self.add_to_cart()
        self.client.post(reverse("shop:coupon_apply"), {"code": coupon.code})
        coupon.valid_to = timezone.now() - timedelta(seconds=1)
        coupon.save()
        response = self.place_order()
        self.assertContains(response, "Промокод истёк")
        self.assertFalse(Order.objects.exists())
        self.client.post(reverse("shop:coupon_remove"))
        self.place_order()
        self.assertEqual(Order.objects.count(), 1)

    def test_order_success_and_history_are_private(self):
        self.client.force_login(self.user)
        self.add_to_cart()
        self.place_order()
        order = Order.objects.get()
        self.assertContains(
            self.client.get(reverse("accounts:profile")), f"Заказ №{order.pk}"
        )
        self.client.logout()
        self.client.force_login(self.other_user)
        self.assertNotContains(
            self.client.get(reverse("accounts:profile")), f"Заказ №{order.pk}"
        )
        self.assertEqual(
            self.client.get(reverse("shop:order_created", args=[order.pk])).status_code,
            404,
        )

    def test_guest_can_see_only_own_confirmation(self):
        self.add_to_cart()
        self.place_order()
        order = Order.objects.get()
        self.assertIsNone(order.user)
        url = reverse("shop:order_created", args=[order.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Client().get(url).status_code, 404)

    def test_review_requires_completed_purchase_and_is_unique(self):
        self.client.force_login(self.user)
        url = reverse("shop:review_add", args=[self.product.pk])
        review = {"rating": 5, "comment": "Очень интересно!"}
        self.client.post(url, review)
        self.assertFalse(Review.objects.exists())
        self.add_to_cart()
        self.place_order()
        self.client.post(url, review)
        self.assertFalse(Review.objects.exists())
        Order.objects.update(status=Order.Status.COMPLETED)
        self.client.post(url, {"rating": 6, "comment": "Тест"})
        self.assertFalse(Review.objects.exists())
        self.client.post(url, review)
        self.client.post(url, review)
        self.assertEqual(Review.objects.count(), 1)
        self.client.force_login(self.other_user)
        self.client.post(url, review)
        self.assertEqual(Review.objects.count(), 1)

    def test_wishlist_is_private_and_toggle_does_not_duplicate(self):
        url = reverse("shop:wishlist_toggle", args=[self.product.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Wishlist.objects.exists())
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertContains(self.client.get(reverse("shop:wishlist")), "Космос")
        self.client.force_login(self.other_user)
        self.assertNotContains(self.client.get(reverse("shop:wishlist")), "Космос")
        self.client.force_login(self.user)
        self.client.post(url)
        self.assertFalse(Wishlist.objects.exists())

    def test_wishlist_does_not_redirect_to_external_site(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("shop:wishlist_toggle", args=[self.product.pk]),
            {"next": "https://example.com/"},
        )
        self.assertRedirects(response, reverse("shop:wishlist"))

    def test_catalog_cache_invalidates_after_save(self):
        self.client.get("/")
        self.assertIsNotNone(cache.get("catalog:products"))
        with self.captureOnCommitCallbacks(execute=True):
            self.product.price = Decimal("777.00")
            self.product.save()
        self.assertIsNone(cache.get("catalog:products"))
        self.assertContains(self.client.get("/"), "777,00 ₽")

    def test_deleted_product_is_removed_from_cart(self):
        self.add_to_cart()
        self.product.delete()
        self.client.get(reverse("shop:cart_detail"))
        self.assertEqual(self.client.session["cart"], {})

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_confirmation_task_contains_order_items_and_total(self):
        self.add_to_cart()
        self.place_order()
        order_confirmation(Order.objects.get().pk)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Космос", mail.outbox[0].body)
        self.assertIn("500.00", mail.outbox[0].body)

    def test_queue_failure_does_not_lose_a_committed_order(self):
        self.add_to_cart()
        with patch("shop.services.order_confirmation.delay", side_effect=OSError):
            with self.assertLogs("shop.services", level="ERROR"):
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.place_order()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertNotIn("cart", self.client.session)

    def test_admin_credentials_order_cards_actions_and_image_upload(self):
        import tempfile

        admin = User.objects.create_superuser(
            username="Lab16", password="Prac4", email="admin@example.com"
        )
        response = self.client.post(
            reverse("admin:login"), {"username": "Lab16", "password": "Prac4"}
        )
        self.assertEqual(response.status_code, 302)
        self.add_to_cart()
        self.place_order()
        order = Order.objects.get()
        response = self.client.get(reverse("admin:shop_order_changelist"))
        self.assertContains(response, "admin-order-card")
        self.client.post(
            reverse("admin:shop_order_changelist"),
            {"action": "mark_completed", "_selected_action": [order.pk]},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)

        image = BytesIO()
        Image.new("RGB", (10, 10), "green").save(image, format="PNG")
        with tempfile.TemporaryDirectory() as media:
            with self.settings(MEDIA_ROOT=media):
                response = self.client.post(
                    reverse("admin:shop_product_change", args=[self.product.pk]),
                    {
                        "name": "Космос",
                        "slug": "cosmos",
                        "category": self.category.pk,
                        "price": "500.00",
                        "stock": 3,
                        "available": "on",
                        "image": SimpleUploadedFile(
                            "cover.png", image.getvalue(), content_type="image/png"
                        ),
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.product.refresh_from_db()
                self.assertTrue(self.product.image.name.endswith(".png"))
                self.assertContains(
                    self.client.get(self.product.get_absolute_url()),
                    self.product.image.url,
                )
        self.assertTrue(admin.is_superuser)

    def test_other_staff_cannot_enter_admin(self):
        self.other_user.is_staff = True
        self.other_user.is_superuser = True
        self.other_user.save()
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)


@skipUnless(connection.vendor == "postgresql", "Блокировки проверяются на PostgreSQL")
@override_settings(CACHES=TEST_CACHE)
class ConcurrentCheckoutTests(TransactionTestCase):
    def test_last_copy_is_sold_once(self):
        category = Category.objects.create(name="Книги", slug="books")
        product = Product.objects.create(
            name="Последняя книга", slug="last", category=category, price=500, stock=1
        )
        barrier = Barrier(2)

        def buy():
            close_old_connections()
            request = SimpleNamespace(session={"cart": {str(product.pk): 1}})
            cart = Cart(request)
            form = OrderCreateForm(order_data())
            assert form.is_valid(), form.errors
            barrier.wait(timeout=10)
            try:
                create_order(cart, form, AnonymousUser())
                return "created"
            except ValidationError:
                return "out_of_stock"
            finally:
                close_old_connections()

        with patch("shop.services.order_confirmation.delay"):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: buy(), range(2)))
        self.assertCountEqual(results, ["created", "out_of_stock"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
