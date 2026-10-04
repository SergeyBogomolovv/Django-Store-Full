from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models

username_validator = RegexValidator(
    r"^[A-Za-z0-9]{6,150}$",
    "Логин: от 6 до 150 символов, только латинские буквы и цифры.",
)
name_validator = RegexValidator(
    r"^[А-Яа-яЁё]+(?: [А-Яа-яЁё]+)*$",
    "Используйте только кириллицу и пробелы.",
)
phone_validator = RegexValidator(
    r"^8\([0-9]{3}\)[0-9]{3}-[0-9]{2}-[0-9]{2}$",
    "Введите телефон в формате 8(XXX)XXX-XX-XX.",
)


class User(AbstractUser):
    username = models.CharField(
        "Логин", max_length=150, unique=True, validators=[username_validator]
    )
    full_name = models.CharField("ФИО", max_length=150, validators=[name_validator])
    phone = models.CharField("Телефон", max_length=15, validators=[phone_validator])
    email = models.EmailField("Email", unique=True)

    def get_full_name(self):
        return self.full_name or super().get_full_name()
