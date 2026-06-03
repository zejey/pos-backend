from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.common.permissions import IsAdmin

from .models import ActivityLog, User
from .serializers import (
    ActivityLogSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services import log_activity


class LoginView(TokenObtainPairView):
    """POST username/password -> access + refresh tokens + user payload."""

    serializer_class = LoginSerializer
    throttle_classes = [ScopedRateThrottle]  # tighter limit on credential attempts
    throttle_scope = "login"


class LogoutView(APIView):
    """Server-side logout (SEC-03): blacklist the supplied refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get("refresh")
        if not token:
            return Response(
                {"detail": "A 'refresh' token is required.", "code": "required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Invalid or expired refresh token.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_activity(request.user, "LOGOUT", entity="User",
                     entity_id=request.user.pk, request=request)
        return Response({"detail": "Logged out."})


class UserViewSet(viewsets.ModelViewSet):
    """Admin-managed user accounts (User Management 1.1)."""

    queryset = User.objects.all().order_by("username")
    permission_classes = [IsAdmin]
    filterset_fields = ["role", "is_active"]
    search_fields = ["username", "first_name", "last_name", "email"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        log_activity(
            self.request.user, "USER_CREATE", entity="User",
            entity_id=user.pk, detail={"username": user.username, "role": user.role},
            request=self.request,
        )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """Current user's own profile (any authenticated role)."""
        return Response(UserSerializer(request.user).data)

    @action(detail=False, methods=["post"], permission_classes=[IsAuthenticated])
    def change_password(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data["old_password"]):
            return Response(
                {"detail": "Old password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        log_activity(user, "PASSWORD_CHANGE", entity="User",
                     entity_id=user.pk, request=request)
        return Response({"detail": "Password updated."})


class ActivityLogViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only audit trail. Admin only."""

    queryset = ActivityLog.objects.select_related("user").all()
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAdmin]
    filterset_fields = ["action", "entity", "user"]
    search_fields = ["action", "entity", "entity_id"]
    ordering_fields = ["created_at"]
