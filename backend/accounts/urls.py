from django.urls import path

from .views import csrf_token, current_user, session_login, session_logout

urlpatterns = [
    path("auth/csrf", csrf_token, name="auth-csrf"),
    path("auth/login", session_login, name="auth-login"),
    path("auth/logout", session_logout, name="auth-logout"),
    path("me", current_user, name="current-user"),
]
