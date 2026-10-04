from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import RegistrationForm


class StoreLoginView(LoginView):
    template_name = "accounts/login.html"

    def form_invalid(self, form):
        messages.error(self.request, "Неверный логин или пароль.")
        return super().form_invalid(form)


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:profile")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Добро пожаловать на Полку!")
        return redirect("shop:product_list")
    return render(request, "accounts/register.html", {"form": form})


@require_POST
def validate_registration(request):
    # Та же серверная форма проверяет поля при вводе и при отправке.
    form = RegistrationForm(request.POST)
    form.is_valid()
    return JsonResponse({"errors": form.errors.get_json_data()})


@login_required
def profile(request):
    orders = request.user.orders.prefetch_related("items__product")
    return render(request, "accounts/profile.html", {"orders": orders})
