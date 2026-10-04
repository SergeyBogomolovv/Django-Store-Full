from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import RegistrationForm

User = get_user_model()


class RegistrationTests(TestCase):
    def setUp(self):
        self.data = {
            "username": "reader123",
            "full_name": "Иванов Иван Иванович",
            "phone": "8(999)123-45-67",
            "email": "reader@example.com",
            "password1": "testpass123",
            "password2": "testpass123",
        }

    def test_registration_creates_user_and_logs_in(self):
        response = self.client.post(reverse("accounts:register"), self.data)
        self.assertRedirects(response, reverse("shop:product_list"))
        user = User.objects.get(username="reader123")
        self.assertTrue(user.check_password("testpass123"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_strict_field_validation(self):
        invalid_values = [
            ("username", "abc12"),
            ("username", "читатель123"),
            ("username", "reader_123"),
            ("full_name", "Ivan Ivanov"),
            ("full_name", "Иван123"),
            ("phone", "+79991234567"),
            ("phone", "8(999)1234567"),
            ("email", "not-an-email"),
            ("password1", "short"),
            ("password2", "different123"),
        ]
        for field, value in invalid_values:
            with self.subTest(field=field, value=value):
                form = RegistrationForm({**self.data, field: value})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_username_and_email_are_unique_ignoring_case(self):
        User.objects.create_user(
            username="Reader123", email="reader@example.com", password="testpass123"
        )
        form = RegistrationForm(self.data)
        self.assertFalse(form.is_valid())
        self.assertIn("username", form.errors)
        self.assertIn("email", form.errors)

    def test_live_validation_returns_errors_without_creating_user(self):
        response = self.client.post(
            reverse("accounts:validate"), {**self.data, "phone": "123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone", response.json()["errors"])
        self.assertFalse(User.objects.exists())

    def test_profile_requires_login_and_logout_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:profile")).status_code, 302)
        self.client.post(reverse("accounts:register"), self.data)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_failure_has_registration_link_and_error(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "wrong", "password": "wrong"}
        )
        self.assertContains(response, "Неверный логин или пароль")
        self.assertContains(response, reverse("accounts:register"))
