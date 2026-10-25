from django.urls import path

from .views import (
    csrf_token,
    current_user,
    email_verification_confirm,
    email_verification_resend,
    invitation_activate,
    invitation_inspect,
    password_reset_confirm,
    password_reset_request,
    session_login,
    session_logout,
)

urlpatterns = [
    path("auth/csrf", csrf_token, name="auth-csrf"),
    path("auth/login", session_login, name="auth-login"),
    path("auth/logout", session_logout, name="auth-logout"),
    path("auth/password-reset", password_reset_request, name="password-reset"),
    path(
        "auth/password-reset/confirm",
        password_reset_confirm,
        name="password-reset-confirm",
    ),
    path(
        "auth/email-verification/confirm",
        email_verification_confirm,
        name="email-verification-confirm",
    ),
    path(
        "auth/email-verification/resend",
        email_verification_resend,
        name="email-verification-resend",
    ),
    path("auth/invitations/inspect", invitation_inspect, name="invitation-inspect"),
    path(
        "auth/invitations/activate",
        invitation_activate,
        name="invitation-activate",
    ),
    path("me", current_user, name="current-user"),
]
