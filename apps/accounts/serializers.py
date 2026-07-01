from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import ActivityLog, User
from .services import log_activity


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        validators=[validate_password],
    )

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "is_active", "date_joined", "last_login", "password",
        ]
        read_only_fields = ["id", "date_joined", "last_login"]

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password is not None:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = [
            "id", "username", "first_name", "last_name", "email",
            "role", "password",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login that embeds the role and records a login activity."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        log_activity(
            self.user,
            "LOGIN",
            entity="User",
            entity_id=self.user.pk,
            request=self.context.get("request"),
        )
        return data


class ActivityLogSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source="user.username", default=None, read_only=True)

    class Meta:
        model = ActivityLog
        fields = [
            "id", "user", "action", "entity", "entity_id",
            "detail", "ip_address", "created_at",
        ]
