import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from academy.models import Student

from .models import AccountInvitation, User

logger = logging.getLogger(__name__)


class InvalidInvitation(Exception):
    """Raised when an invitation cannot be inspected or consumed."""


class InvitationAlreadyPending(Exception):
    """Raised when a student already has a usable invitation."""


@dataclass
class InvitationDetails:
    email: str | None
    first_name: str
    last_name: str
    student_name: str | None = None


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


@transaction.atomic
def issue_student_invitation(*, student_id: int, email: str, created_by):
    """Issue one email-bound invitation for an existing, unlinked student.

    A row lock serializes invitations for the same student. An expired pending
    invitation is retained as an audited replacement; an unexpired one is never
    silently invalidated.
    """
    if not email or not email.strip():
        raise ValidationError({"email": "Ingresá el correo del destinatario."})
    normalized_email = User.objects.normalize_email(email)
    student = Student.objects.select_for_update().get(pk=student_id)
    if student.user_id is not None:
        raise ValidationError({"student": "Este alumno ya tiene una cuenta vinculada."})
    if User.objects.filter(
        email__iexact=normalized_email,
        student_record__isnull=False,
    ).exists():
        raise ValidationError(
            {"email": "Esta cuenta ya está asociada a otro alumno."}
        )

    now = timezone.now()
    other_pending_invitations = AccountInvitation.objects.select_for_update().filter(
        student__isnull=False,
        email__iexact=normalized_email,
        consumed_at__isnull=True,
        revoked_at__isnull=True,
    ).exclude(student=student)
    for previous_invitation in other_pending_invitations:
        if previous_invitation.expires_at > now:
            raise InvitationAlreadyPending
        previous_invitation.revoked_at = now
        previous_invitation.revoked_by = created_by
        previous_invitation.revocation_reason = (
            "Vencida y reemplazada por una invitación para otro alumno."
        )
        previous_invitation.save(
            update_fields=("revoked_at", "revoked_by", "revocation_reason")
        )

    previous_invitation = (
        AccountInvitation.objects.select_for_update()
        .filter(
            student=student,
            consumed_at__isnull=True,
            revoked_at__isnull=True,
        )
        .first()
    )
    if previous_invitation:
        if previous_invitation.expires_at > now:
            raise InvitationAlreadyPending
        previous_invitation.revoked_at = now
        previous_invitation.revoked_by = created_by
        previous_invitation.revocation_reason = (
            "Vencida y reemplazada por una nueva invitación."
        )
        previous_invitation.save(
            update_fields=("revoked_at", "revoked_by", "revocation_reason")
        )

    token = secrets.token_urlsafe(32)
    invitation = AccountInvitation(
        token_hash=_token_hash(token),
        email=normalized_email,
        first_name=student.first_name,
        last_name=student.last_name,
        created_by=created_by,
        student=student,
        expires_at=now + timedelta(days=7),
    )
    invitation.full_clean()
    try:
        with transaction.atomic():
            invitation.save(force_insert=True)
    except IntegrityError as error:
        # Partial unique constraints remain authoritative for competing requests.
        raise InvitationAlreadyPending from error
    return invitation, token


def send_student_invitation_email(invitation: AccountInvitation, token: str) -> bool:
    """Send the one-time link without exposing or logging its token."""
    url = f"{settings.FRONTEND_BASE_URL}/activar#{token}"
    try:
        return bool(
            send_mail(
                subject="Tenés una invitación a Cianci",
                message=(
                    f"La administración de Cianci te invitó a consultar la información "
                    f"académica de {invitation.first_name} {invitation.last_name}.\n\n"
                    f"Abrí este enlace para continuar: {url}\n\n"
                    "El enlace vence en siete días. Si no esperabas esta invitación, "
                    "podés ignorar este mensaje."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[invitation.email],
                fail_silently=False,
            )
        )
    except Exception:
        logger.warning("No se pudo enviar una invitación académica.", exc_info=False)
        return False


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
        student_name=(str(invitation.student) if invitation.student_id else None),
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
            if invitation.student_id is None:
                invitation.claimed_user = user
                invitation.consumed_at = now
                invitation.save(update_fields=("claimed_user", "consumed_at"))
    except IntegrityError as exc:
        # The database uniqueness constraint is authoritative across concurrent claims.
        raise InvalidInvitation from exc

    return user


@transaction.atomic
def accept_student_invitation(*, invitation_id: int, user: User) -> AccountInvitation:
    """Link the authenticated, verified recipient to the existing student."""
    reference = AccountInvitation.objects.only("student_id").get(
        pk=invitation_id, student__isnull=False
    )
    student = Student.objects.select_for_update().get(pk=reference.student_id)
    invitation = AccountInvitation.objects.select_for_update().get(pk=invitation_id)
    locked_user = User.objects.select_for_update().get(pk=user.pk)
    now = timezone.now()

    if invitation.student_id != student.pk:
        raise InvalidInvitation
    if (
        invitation.consumed_at is not None
        or invitation.revoked_at is not None
        or invitation.expires_at <= now
        or invitation.email != locked_user.email
        or locked_user.email_verified_at is None
        or (
            invitation.claimed_user_id is not None
            and invitation.claimed_user_id != locked_user.pk
        )
    ):
        raise InvalidInvitation
    if student.user_id is not None:
        raise ValidationError(
            {"invitation": "Este alumno ya tiene una cuenta vinculada."}
        )
    if Student.objects.filter(user=locked_user).exclude(pk=student.pk).exists():
        raise ValidationError(
            {"invitation": "Esta cuenta ya está asociada a otro alumno."}
        )

    student.user = locked_user
    student.save(update_fields=("user", "updated_at"))
    invitation.accepted_by = locked_user
    invitation.consumed_at = now
    invitation.save(update_fields=("accepted_by", "consumed_at"))
    return invitation


@transaction.atomic
def revoke_student_invitation(*, invitation_id: int, student_id: int, actor: User):
    """Cancel an unused student invitation while retaining the audit trail."""
    student = Student.objects.select_for_update().get(pk=student_id)
    invitation = AccountInvitation.objects.select_for_update().get(
        pk=invitation_id, student=student
    )
    if invitation.consumed_at is not None or invitation.revoked_at is not None:
        raise ValidationError({"invitation": "La invitación ya no está pendiente."})
    invitation.revoked_at = timezone.now()
    invitation.revoked_by = actor
    invitation.revocation_reason = "Cancelada desde el panel administrativo."
    invitation.save(update_fields=("revoked_at", "revoked_by", "revocation_reason"))
    return invitation


@transaction.atomic
def revoke_student_account_link(*, student_id: int) -> Student:
    """Remove the current account association without altering student records."""
    student = Student.objects.select_for_update().get(pk=student_id)
    if student.user_id is None:
        raise ValidationError({"student": "Este alumno no tiene una cuenta vinculada."})
    student.user = None
    student.save(update_fields=("user", "updated_at"))
    return student
