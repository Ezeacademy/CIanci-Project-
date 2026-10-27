import json
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.cache import add_never_cache_headers
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from adminpanel.permissions import can_access_admin_panel

from .email_verification import (
    InvalidVerificationToken,
    confirm_verification_token,
    send_verification_email,
)
from .invitations import InvalidInvitation, activate_invitation, inspect_invitation
from .models import User
from .throttles import (
    PasswordResetEmailThrottle,
    PasswordResetIPThrottle,
    VerificationResendThrottle,
)

logger = logging.getLogger(__name__)


@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    response = JsonResponse({"csrfToken": get_token(request)})
    add_never_cache_headers(response)
    return response


@require_POST
@csrf_protect
def session_login(request):
    if request.content_type != "application/json":
        return JsonResponse({"detail": "Solicitud inválida."}, status=400)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"detail": "Solicitud inválida."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"detail": "Solicitud inválida."}, status=400)
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return JsonResponse({"detail": "Solicitud inválida."}, status=400)

    user = authenticate(request, email=email, password=password)
    if user is None:
        return JsonResponse(
            {"detail": "El email o la contraseña no son correctos."}, status=400
        )

    login(request, user)
    response = JsonResponse({"detail": "Sesión iniciada."})
    add_never_cache_headers(response)
    return response


@require_POST
@csrf_protect
def session_logout(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "La sesión no está autenticada."}, status=403)
    logout(request)
    response = JsonResponse({"detail": "Sesión cerrada."})
    add_never_cache_headers(response)
    return response


def _invitation_json(request):
    if request.content_type != "application/json":
        return None
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _invalid_invitation_response():
    response = JsonResponse(
        {"detail": "La invitación no es válida o ya no está disponible."},
        status=400,
    )
    add_never_cache_headers(response)
    return response


@require_POST
@csrf_protect
def invitation_inspect(request):
    if request.user.is_authenticated:
        return _invalid_invitation_response()
    payload = _invitation_json(request)
    if payload is None or not isinstance(payload.get("token"), str):
        return _invalid_invitation_response()
    try:
        details = inspect_invitation(payload["token"])
    except InvalidInvitation:
        return _invalid_invitation_response()

    response = JsonResponse(
        {
            "email": details.email,
            "emailBound": details.email is not None,
            "firstName": details.first_name,
            "lastName": details.last_name,
        }
    )
    add_never_cache_headers(response)
    return response


@require_POST
@csrf_protect
def invitation_activate(request):
    if request.user.is_authenticated:
        return _invalid_invitation_response()
    payload = _invitation_json(request)
    required_strings = (
        "token",
        "email",
        "firstName",
        "lastName",
        "password",
        "passwordConfirmation",
    )
    if payload is None or any(
        not isinstance(payload.get(field), str) for field in required_strings
    ):
        return _invalid_invitation_response()
    if payload["password"] != payload["passwordConfirmation"]:
        response = JsonResponse(
            {"errors": {"passwordConfirmation": ["Las contraseñas no coinciden."]}},
            status=400,
        )
        add_never_cache_headers(response)
        return response

    try:
        user = activate_invitation(
            token=payload["token"],
            email=payload["email"],
            first_name=payload["firstName"],
            last_name=payload["lastName"],
            password=payload["password"],
        )
    except InvalidInvitation:
        return _invalid_invitation_response()
    except ValidationError as exc:
        messages = getattr(exc, "message_dict", None)
        errors = messages or {"password": exc.messages}
        response = JsonResponse({"errors": errors}, status=400)
        add_never_cache_headers(response)
        return response

    login(request, user)
    send_verification_email(user)
    response = JsonResponse({"detail": "Cuenta activada."}, status=201)
    add_never_cache_headers(response)
    return response


@api_view(["GET"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    response = Response(
        {
            "id": user.pk,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "emailVerified": user.email_verified_at is not None,
            "canAccessAdminPanel": can_access_admin_panel(user),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetIPThrottle, PasswordResetEmailThrottle])
def password_reset_request(request):
    email = request.data.get("email", "")
    if isinstance(email, str) and email.strip():
        form = PasswordResetForm({"email": email.strip()})
        if form.is_valid():
            try:
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name="accounts/password_reset_email.html",
                    subject_template_name="accounts/password_reset_subject.txt",
                    extra_email_context={
                        "frontend_base_url": settings.FRONTEND_BASE_URL
                    },
                )
            except Exception:
                logger.warning("No se pudo procesar un correo de recuperación.")
    return Response(
        {"detail": "Si la cuenta puede recuperar su contraseña, recibirá un enlace."},
        status=202,
    )


@csrf_protect
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    password = request.data.get("password")
    confirmation = request.data.get("passwordConfirmation")
    invalid = Response({"detail": "El enlace no es válido o venció."}, status=400)
    if not all(
        isinstance(value, str) and value
        for value in (uidb64, token, password, confirmation)
    ):
        return invalid
    if password != confirmation:
        return Response(
            {"errors": {"passwordConfirmation": ["Las contraseñas no coinciden."]}},
            status=400,
        )
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=user_id)
            if not default_token_generator.check_token(user, token):
                return invalid
            form = SetPasswordForm(
                user,
                {"new_password1": password, "new_password2": confirmation},
            )
            if not form.is_valid():
                return Response({"errors": form.errors}, status=400)
            form.save()
    except (User.DoesNotExist, ValueError, TypeError):
        return invalid
    return Response({"detail": "La contraseña se actualizó. Ya podés ingresar."})


@csrf_protect
@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def email_verification_confirm(request):
    token = request.data.get("token")
    if not isinstance(token, str) or not token:
        return Response({"detail": "El enlace no es válido o venció."}, status=400)
    try:
        with transaction.atomic():
            confirm_verification_token(token)
    except InvalidVerificationToken:
        return Response({"detail": "El enlace no es válido o venció."}, status=400)
    return Response({"detail": "Email verificado.", "emailVerified": True})


@csrf_protect
@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
@throttle_classes([VerificationResendThrottle])
def email_verification_resend(request):
    user = request.user
    if user.email_verified_at is None:
        send_verification_email(user)
    return Response(
        {"detail": "Si tu email necesita verificación, recibirás un nuevo enlace."},
        status=200,
    )


# DRF marks APIView callbacks csrf_exempt; these public POST actions still need
# Django's middleware CSRF check even when the caller has no authenticated session.
for _csrf_protected_view in (
    password_reset_request,
    password_reset_confirm,
    email_verification_confirm,
    email_verification_resend,
):
    _csrf_protected_view.csrf_exempt = False
