# Полка

Учебный книжный магазин на Django 5.2: каталог, поиск и фильтры, корзина,
заказы, регистрация, личный кабинет, отзывы, избранное и промокоды.

## Запуск в Docker

Нужны Docker Desktop (или Docker Engine с Compose) и Python 3 для создания `.env`.

```sh
python3 setup_env.py
docker compose up --build -d
```

На Windows вместо `python3` используйте `python`.

Магазин: http://localhost:8000 · Админка: http://localhost:8000/admin/

Администратор: **Lab16 / Prac4**. При первом запуске
автоматически создаются 8 книг и промокоды **POLKA10** (10%) и **BOOK200** (200 ₽).
Повторный запуск не сбрасывает заказы, остатки и пароль.

```sh
docker compose logs -f web celery_worker
docker compose down
```

## Локально без Docker

Python 3.11+. Используются SQLite и кеш в памяти; задачи Celery выполняются сразу.

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup_env.py
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

В PowerShell активация: `.venv\Scripts\Activate.ps1`.
Локальная и контейнерная базы независимы.

## Проверка

```sh
docker compose exec web python manage.py test
```

Без Docker: `python manage.py test`. Тест одновременной покупки последней книги
работает только на PostgreSQL; остальные проверки выполняются и на SQLite.

СБП работает без банковской интеграции: оплату отмечает администратор.
Подтверждения заказов выводятся в консоль Celery worker.

## Cloudflare (при наличии домена)

Локально не подключён: нужны ваш домен и токен.
В [Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/get-started/)
создайте туннель с маршрутом домена на `http://nginx:80`.
Добавьте в `.env` токен `CLOUDFLARE_TUNNEL_TOKEN`, домен в `DJANGO_ALLOWED_HOSTS`
(сохранив localhost и 127.0.0.1) и `https://ваш-домен` в
`DJANGO_CSRF_TRUSTED_ORIGINS`. Включите Always Use HTTPS и запустите:

```sh
docker compose -f docker-compose.yml -f docker-compose.cloudflare.yml up -d
```

Для `/static/*` и `/media/*` оставьте кеширование с учётом заголовков nginx;
для остальных путей задайте [Bypass cache](https://developers.cloudflare.com/cache/how-to/cache-rules/settings/).
