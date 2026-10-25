import hashlib
import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from .models import User

logger = logging.getLogger(__name__)
TOKEN_SALT = "accounts.email-verification.v1"


class InvalidVerificationToken(Exception):
    pass


def _email_digest(email):
    return hashlib.sha256(email.casefold().encode()).hexdigest()


def create_verification_token(user):
    return signing.dumps(
        {"user_id": user.pk, "email": _email_digest(user.email)}, salt=TOKEN_SALT
    )


def confirm_verification_token(token):
    try:
        payload = signing.loads(
            token, salt=TOKEN_SALT, max_age=settings.EMAIL_VERIFICATION_TIMEOUT
        )
        user = User.objects.select_for_update().get(pk=payload["user_id"])
        if not constant_time_compare(
            payload.get("email", ""), _email_digest(user.email)
        ):
            raise InvalidVerificationToken
    except (signing.BadSignature, KeyError, TypeError, User.DoesNotExist) as exc:
        raise InvalidVerificationToken from exc
    if user.email_verified_at is None:
        user.email_verified_at = timezone.now()
        user.save(update_fields=["email_verified_at"])
    return user


def send_verification_email(user):
    token = create_verification_token(user)
    url = f"{settings.FRONTEND_BASE_URL}/verificar-email#{token}"
    try:
        send_mail(
            subject="Verificá tu email | Cianci",
            message=(
                "Confirmá que controlás esta dirección de email abriendo el enlace: "
                f"{url}\n\nEl enlace vence en 24 horas."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception:
        logger.warning("No se pudo enviar un correo de verificación.", exc_info=False)
        return False
