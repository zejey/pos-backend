from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import ActivityLog, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "role", "is_active", "is_staff", "last_login")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (("Role", {"fields": ("role",)}),)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "entity", "entity_id")
    list_filter = ("action", "entity")
    search_fields = ("action", "entity", "entity_id")
    readonly_fields = [f.name for f in ActivityLog._meta.fields]
