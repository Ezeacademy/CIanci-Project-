import hashlib
import secrets
from dataclasses import dataclass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import AccountInvitation, User


class InvalidInvitation(Exception):
    """Raised when an invitation cannot be inspected or consumed."""


@dataclass
class InvitationDetails:
    email: str | None
    first_name: str
    last_name: str


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_invitation(*, email, first_name, last_name, expires_at, created_by):
    if expires_at <= timezone.now():
        raise ValidationError({"expires_at": "La invitación debe vencer en el futuro."})

    token = secrets.token_urlsafe(32)
    email = User.objects.normalize_email(email) if email else None
    invitation = AccountInvitation.objects.create(
        token_hash=_token_hash(token),
        email=email,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        expires_at=expires_at,
        created_by=created_by,
    )
    return invitation, token


def inspect_invitation(token: str) -> InvitationDetails:
    if not token or len(token) > 128:
        raise InvalidInvitation
    try:
        invitation = AccountInvitation.objects.get(token_hash=_token_hash(token))
    except AccountInvitation.DoesNotExist as exc:
        raise InvalidInvitation from exc

    if (
        invitation.consumed_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= timezone.now()
    ):
        raise InvalidInvitation
    return InvitationDetails(
        email=invitation.email,
        first_name=invitation.first_name,
        last_name=invitation.last_name,
    )


def activate_invitation(
    *, token: str, email: str, first_name: str, last_name: str, password: str
) -> User:
    details = inspect_invitation(token)
    email = User.objects.normalize_email(email)
    if details.email and email != details.email:
        raise InvalidInvitation

    user = User(email=email, first_name=first_name.strip(), last_name=last_name.strip())
    user.set_password(password)
    user.full_clean()
    validate_password(password, user=user)

    try:
        with transaction.atomic():
            try:
                invitation = AccountInvitation.objects.select_for_update().get(
                    token_hash=_token_hash(token)
                )
            except AccountInvitation.DoesNotExist as exc:
                raise InvalidInvitation from exc

            now = timezone.now()
            if (
                invitation.consumed_at is not None
                or invitation.revoked_at is not None
                or invitation.expires_at <= now
                or (invitation.email and email != invitation.email)
            ):
                raise InvalidInvitation
            user.save(force_insert=True)
            invitation.claimed_user = user
            invitation.consumed_at = now
            invitation.save(update_fields=("claimed_user", "consumed_at"))
    except IntegrityError as exc:
        # The database uniqueness constraint is authoritative across concurrent claims.
        raise InvalidInvitation from exc

    return user
