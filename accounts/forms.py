from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    password1 = forms.CharField(
        label="Пароль",
        min_length=8,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Не менее 8 символов.",
    )

    class Meta:
        model = User
        fields = ["username", "full_name", "phone", "email", "password1", "password2"]
        widgets = {
            "username": forms.TextInput(
                attrs={"autocomplete": "username", "minlength": 6}
            ),
            "full_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "phone": forms.TextInput(
                attrs={"placeholder": "8(999)123-45-67", "autocomplete": "tel"}
            ),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }

    def clean_username(self):
        username = self.cleaned_data["username"]
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("Этот логин уже занят.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Этот email уже зарегистрирован.")
        return email
