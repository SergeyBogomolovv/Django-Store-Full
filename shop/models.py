from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from accounts.models import name_validator, phone_validator


class Category(models.Model):
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Адрес", max_length=200, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "категория"
        verbose_name_plural = "категории"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("shop:product_list_by_category", args=[self.slug])


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        related_name="products",
        on_delete=models.CASCADE,
        verbose_name="Категория",
    )
    name = models.CharField("Название", max_length=200)
    slug = models.SlugField("Адрес", max_length=200, unique=True)
    author = models.CharField("Автор", max_length=150, blank=True)
    description = models.TextField("Описание", blank=True)
    price = models.DecimalField(
        "Цена",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    stock = models.PositiveIntegerField("Остаток", default=0)
    available = models.BooleanField("Доступен", default=True)
    image = models.ImageField("Изображение", upload_to="products/%Y/%m/%d", blank=True)
    created = models.DateTimeField("Создан", auto_now_add=True)
    updated = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["-created", "-pk"]
        verbose_name = "товар"
        verbose_name_plural = "товары"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0), name="product_positive_price"
            ),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("shop:product_detail", args=[self.slug])


class Coupon(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Процент"
        FIXED = "fixed", "Сумма в рублях"

    code = models.CharField(
        "Промокод",
        max_length=30,
        unique=True,
        validators=[RegexValidator(r"^[A-Za-z0-9]+$", "Только латиница и цифры.")],
    )
    kind = models.CharField("Тип скидки", max_length=10, choices=Kind.choices)
    value = models.DecimalField(
        "Размер скидки",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    active = models.BooleanField("Активен", default=True)
    valid_from = models.DateTimeField("Действует с", default=timezone.now)
    valid_to = models.DateTimeField("Действует до")

    class Meta:
        verbose_name = "промокод"
        verbose_name_plural = "промокоды"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(value__gt=0), name="coupon_positive_value"
            ),
            models.CheckConstraint(
                condition=~models.Q(kind="percent") | models.Q(value__lte=100),
                name="coupon_percent_at_most_100",
            ),
        ]

    def __str__(self):
        return self.code

    def clean(self):
        super().clean()
        self.code = self.code.upper()
        if self.kind == self.Kind.PERCENT and self.value and self.value > 100:
            raise ValidationError({"value": "Процент скидки не может превышать 100."})
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValidationError({"valid_to": "Укажите дату позже начала действия."})

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)

    def is_valid(self):
        return self.active and self.valid_from <= timezone.now() <= self.valid_to

    def get_discount(self, subtotal):
        if self.kind == self.Kind.PERCENT:
            discount = subtotal * self.value / 100
        else:
            discount = self.value
        return min(discount, subtotal).quantize(Decimal("0.01"))


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Новый"
        PROCESSING = "processing", "В обработке"
        SHIPPED = "shipped", "Отправлен"
        COMPLETED = "completed", "Завершено"
        CANCELED = "canceled", "Отменён"

    class Delivery(models.TextChoices):
        COURIER = "courier", "Курьером"
        PICKUP = "pickup", "Самовывоз"

    class Payment(models.TextChoices):
        ON_RECEIPT = "on_receipt", "При получении"
        SBP = "sbp", "Перевод по СБП"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="orders",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Покупатель",
    )
    first_name = models.CharField("Имя", max_length=50, validators=[name_validator])
    last_name = models.CharField("Фамилия", max_length=50, validators=[name_validator])
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=15, validators=[phone_validator])
    address = models.CharField("Адрес", max_length=250, blank=True)
    postal_code = models.CharField(
        "Индекс",
        max_length=6,
        blank=True,
        validators=[RegexValidator(r"^[0-9]{6}$", "Индекс должен содержать 6 цифр.")],
    )
    city = models.CharField("Город", max_length=100, blank=True)
    delivery_method = models.CharField(
        "Доставка", max_length=10, choices=Delivery.choices, default=Delivery.COURIER
    )
    delivery_date = models.DateField("Дата доставки")
    payment_method = models.CharField(
        "Оплата", max_length=15, choices=Payment.choices, default=Payment.ON_RECEIPT
    )
    status = models.CharField(
        "Статус", max_length=15, choices=Status.choices, default=Status.NEW
    )
    paid = models.BooleanField("Оплачен", default=False)
    coupon_code = models.CharField("Промокод", max_length=30, blank=True)
    discount = models.DecimalField(
        "Скидка",
        max_digits=12,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    created = models.DateTimeField("Создан", auto_now_add=True)
    updated = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ["-created", "-pk"]
        verbose_name = "заказ"
        verbose_name_plural = "заказы"

    def __str__(self):
        return f"Заказ №{self.pk}"

    def get_subtotal(self):
        return sum((item.get_cost() for item in self.items.all()), Decimal("0.00"))

    def get_total_cost(self):
        return max(self.get_subtotal() - self.discount, Decimal("0.00"))


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, related_name="items", on_delete=models.CASCADE, verbose_name="Заказ"
    )
    product = models.ForeignKey(
        Product,
        related_name="order_items",
        on_delete=models.PROTECT,
        verbose_name="Товар",
    )
    product_name = models.CharField("Название при покупке", max_length=200)
    price = models.DecimalField(
        "Цена при покупке",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    quantity = models.PositiveIntegerField(
        "Количество", default=1, validators=[MinValueValidator(1)]
    )

    class Meta:
        verbose_name = "позиция заказа"
        verbose_name_plural = "состав заказа"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="order_item_positive_quantity"
            ),
        ]

    def __str__(self):
        return self.product_name

    def get_cost(self):
        return self.price * self.quantity


class Review(models.Model):
    product = models.ForeignKey(
        Product, related_name="reviews", on_delete=models.CASCADE, verbose_name="Товар"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Покупатель"
    )
    rating = models.PositiveSmallIntegerField(
        "Оценка", choices=[(n, str(n)) for n in range(1, 6)]
    )
    comment = models.TextField("Отзыв", max_length=2000)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "отзыв"
        verbose_name_plural = "отзывы"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "user"], name="one_review_per_product"
            ),
            models.CheckConstraint(
                condition=models.Q(rating__gte=1, rating__lte=5),
                name="review_rating_between_1_and_5",
            ),
        ]

    def __str__(self):
        return f"{self.product}: {self.rating}/5"


class Wishlist(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="wishlist",
        on_delete=models.CASCADE,
        verbose_name="Покупатель",
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "избранный товар"
        verbose_name_plural = "избранное"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_wishlist_product"
            ),
        ]
