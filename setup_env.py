"""Создать локальный .env со случайными ключами; существующий файл не менять."""

import secrets
from pathlib import Path

root = Path(__file__).resolve().parent
destination = root / ".env"

if destination.exists():
    print(".env уже существует, оставлен без изменений.")
else:
    content = (root / ".env.example").read_text(encoding="utf-8")
    content = content.replace(
        "DJANGO_SECRET_KEY=\n", f"DJANGO_SECRET_KEY={secrets.token_urlsafe(50)}\n"
    )
    content = content.replace(
        "POSTGRES_PASSWORD=\n", f"POSTGRES_PASSWORD={secrets.token_urlsafe(24)}\n"
    )
    destination.write_text(content, encoding="utf-8")
    destination.chmod(0o600)
    print(".env создан. Теперь можно запускать проект.")
