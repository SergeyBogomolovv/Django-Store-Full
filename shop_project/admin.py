from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError


class StoreAdminLoginForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.username != "Lab16":
            raise ValidationError(
                "Для этой админки используйте учебную учётную запись."
            )


class StoreAdminSite(AdminSite):
    site_header = "Полка — управление магазином"
    site_title = "Полка"
    index_title = "Магазин"
    login_form = StoreAdminLoginForm

    def has_permission(self, request):
        return super().has_permission(request) and request.user.username == "Lab16"
