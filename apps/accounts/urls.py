from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ActivityLogViewSet, LoginView, LogoutView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("activity", ActivityLogViewSet, basename="activity")

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("", include(router.urls)),
]
