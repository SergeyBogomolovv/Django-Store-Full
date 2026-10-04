from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class StoreUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Данные покупателя", {"fields": ("full_name", "phone")}),
    )
    list_display = ("username", "full_name", "email", "phone", "is_staff")

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Данные покупателя", {"fields": ("email", "full_name", "phone")}),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.username == "Lab16":
            return ("username",)
        return ()
