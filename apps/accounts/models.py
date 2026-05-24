from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """System user. Role-based access per the brief: Admin and Cashier."""

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        CASHIER = "CASHIER", "Cashier"

    role = models.CharField(
        max_length=10, choices=Role.choices, default=Role.CASHIER
    )

    @property
    def is_admin(self):
        # Django superusers are always treated as admins.
        return self.is_superuser or self.role == self.Role.ADMIN

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class ActivityLog(models.Model):
    """Immutable audit trail of who did what (User Management 1.3)."""

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="activities",
    )
    action = models.CharField(max_length=120)
    entity = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=60, blank=True)
    detail = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action"]),
            models.Index(fields=["entity", "entity_id"]),
        ]

    def __str__(self):
        who = self.user.username if self.user else "system"
        return f"{who}: {self.action}"
