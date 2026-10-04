from django.contrib.admin.apps import AdminConfig


class StoreAdminConfig(AdminConfig):
    default_site = "shop_project.admin.StoreAdminSite"
