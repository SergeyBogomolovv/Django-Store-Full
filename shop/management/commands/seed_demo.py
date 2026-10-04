import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from shop.models import Category, Coupon, Product


class Command(BaseCommand):
    help = "Добавить учебного администратора, книги и промокоды, не дублируя записи."

    def handle(self, *args, **options):
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not password:
            raise CommandError("Задайте DJANGO_SUPERUSER_PASSWORD в .env.")

        user, created = get_user_model().objects.get_or_create(
            username="Lab16",
            defaults={
                "email": "admin@polka.example",
                "is_staff": True,
                "is_superuser": True,
                "full_name": "Администратор Магазина",
                "phone": "8(999)000-00-00",
            },
        )
        if created:
            user.set_password(password)
            user.save()

        categories = {}
        for slug, name in [
            ("fiction", "Художественная"),
            ("science", "Научпоп"),
            ("technology", "Технологии"),
            ("art", "Искусство"),
        ]:
            categories[slug], _ = Category.objects.get_or_create(
                slug=slug, defaults={"name": name}
            )

        books = [
            (
                "cosmos",
                "Космос",
                "Карл Саган",
                "science",
                "890.00",
                "О Вселенной, звёздах, открытиях и нашем месте в космосе.",
            ),
            (
                "monday",
                "Понедельник начинается в субботу",
                "Братья Стругацкие",
                "fiction",
                "690.00",
                "Повесть о людях, для которых научный поиск неотделим от волшебства.",
            ),
            (
                "python",
                "Погружение в Python",
                "Марк Пилгрим",
                "technology",
                "1290.00",
                "От первых программ на Python до работы с данными.",
            ),
            (
                "art",
                "История искусства",
                "Эрнст Гомбрих",
                "art",
                "1590.00",
                "Путешествие по живописи, скульптуре и архитектуре разных эпох.",
            ),
            (
                "planet",
                "Маленький принц",
                "Антуан де Сент-Экзюпери",
                "fiction",
                "490.00",
                "История о дружбе, ответственности и умении видеть самое важное.",
            ),
            (
                "time",
                "Краткая история времени",
                "Стивен Хокинг",
                "science",
                "790.00",
                "Чёрные дыры, пространство и время в доступном рассказе о физике.",
            ),
            (
                "algorithms",
                "Грокаем алгоритмы",
                "Адитья Бхаргава",
                "technology",
                "1190.00",
                "Наглядно о поиске, сортировке и работе с графами.",
            ),
            (
                "design",
                "Дизайн привычных вещей",
                "Дональд Норман",
                "art",
                "990.00",
                "Почему одними вещами удобно пользоваться, а другие вызывают вопросы.",
            ),
        ]
        for slug, name, author, category, price, description in books:
            Product.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "author": author,
                    "category": categories[category],
                    "price": Decimal(price),
                    "stock": 12,
                    "description": description,
                },
            )
        for code, kind, value in [
            ("POLKA10", Coupon.Kind.PERCENT, 10),
            ("BOOK200", Coupon.Kind.FIXED, 200),
        ]:
            Coupon.objects.get_or_create(
                code=code,
                defaults={
                    "kind": kind,
                    "value": value,
                    "valid_to": timezone.now() + timedelta(days=365),
                },
            )
        self.stdout.write(
            self.style.SUCCESS(
                "Готово: 8 книг, 4 категории, POLKA10 / BOOK200. Администратор: Lab16."
            )
        )
