import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils.cache import add_never_cache_headers
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


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
        }
    )
    response["Cache-Control"] = "no-store"
    return response
