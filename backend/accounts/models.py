from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(_("Correo electrónico"), unique=True)
    email_verified_at = models.DateTimeField(
        _("Fecha de verificación del correo"), null=True, blank=True
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = _("Usuario")
        verbose_name_plural = _("Usuarios")
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="accounts_user_email_ci_unique"
            ),
        ]

    def clean(self):
        super().clean()
        self.email = type(self).objects.normalize_email(self.email)

    def save(self, *args, **kwargs):
        self.email = type(self).objects.normalize_email(self.email)
        update_fields = kwargs.get("update_fields")
        if self.pk and (update_fields is None or "email" in update_fields):
            previous_email = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("email", flat=True)
                .first()
            )
            if (
                previous_email is not None
                and previous_email.casefold() != self.email.casefold()
            ):
                self.email_verified_at = None
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"email_verified_at"}
        super().save(*args, **kwargs)


class AccountInvitation(models.Model):
    token_hash = models.CharField(_("Hash del token"), max_length=64, unique=True)
    email = models.EmailField(_("Correo electrónico"), blank=True, null=True)
    first_name = models.CharField(_("Nombre"), max_length=150, blank=True)
    last_name = models.CharField(_("Apellido"), max_length=150, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Creada por"),
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_account_invitations",
    )
    claimed_user = models.OneToOneField(
        "accounts.User",
        verbose_name=_("Cuenta activada"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="account_invitation",
    )
    accepted_by = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Cuenta que aceptó el vínculo"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accepted_student_invitations",
    )
    student = models.ForeignKey(
        "academy.Student",
        verbose_name=_("Alumno vinculado"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="account_invitations",
    )
    revoked_by = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Revocada por"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_account_invitations",
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    expires_at = models.DateTimeField(_("Vence el"))
    consumed_at = models.DateTimeField(_("Fecha de uso"), null=True, blank=True)
    revoked_at = models.DateTimeField(_("Fecha de revocación"), null=True, blank=True)
    revocation_reason = models.CharField(
        _("Motivo de revocación"), max_length=200, blank=True
    )

    class Meta:
        verbose_name = _("Invitación de cuenta")
        verbose_name_plural = _("Invitaciones de cuentas")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(consumed_at__isnull=True)
                | models.Q(revoked_at__isnull=True),
                name="accounts_invite_not_consumed_and_revoked",
            ),
            models.CheckConstraint(
                condition=models.Q(consumed_at__isnull=True)
                | models.Q(claimed_user__isnull=False)
                | models.Q(accepted_by__isnull=False),
                name="accounts_invite_consumed_has_account",
            ),
            models.CheckConstraint(
                condition=models.Q(student__isnull=True)
                | models.Q(email__isnull=False),
                name="accounts_student_invite_requires_email",
            ),
            models.UniqueConstraint(
                fields=("student",),
                condition=(
                    models.Q(student__isnull=False)
                    & models.Q(consumed_at__isnull=True)
                    & models.Q(revoked_at__isnull=True)
                ),
                name="accounts_one_pending_student_invite",
            ),
            models.UniqueConstraint(
                Lower("email"),
                condition=(
                    models.Q(student__isnull=False)
                    & models.Q(consumed_at__isnull=True)
                    & models.Q(revoked_at__isnull=True)
                ),
                name="accounts_one_pending_student_invite_email",
            ),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return self.email or f"Invitación {self.pk}"


class GuardianRelationship(models.Model):
    guardian = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Tutor"),
        on_delete=models.PROTECT,
        related_name="guardian_relationships",
    )
    student = models.ForeignKey(
        "academy.Student",
        verbose_name=_("Alumno"),
        on_delete=models.PROTECT,
        related_name="guardian_relationships",
    )
    created_at = models.DateTimeField(_("Fecha de creación"), auto_now_add=True)
    created_by = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Creado por"),
        on_delete=models.PROTECT,
        related_name="created_guardian_relationships",
    )
    revoked_at = models.DateTimeField(_("Fecha de revocación"), null=True, blank=True)
    revoked_by = models.ForeignKey(
        "accounts.User",
        verbose_name=_("Revocado por"),
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="revoked_guardian_relationships",
    )

    class Meta:
        verbose_name = _("Vínculo de tutor")
        verbose_name_plural = _("Vínculos de tutores")
        constraints = [
            models.UniqueConstraint(
                fields=("student", "guardian"),
                condition=models.Q(revoked_at__isnull=True),
                name="accounts_active_guardian_link_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(revoked_at__isnull=True, revoked_by__isnull=True)
                    | models.Q(revoked_at__isnull=False, revoked_by__isnull=False)
                ),
                name="accounts_guardian_revocation_audit_pair",
            ),
        ]
        ordering = ("student_id", "guardian_id", "created_at")

    def __str__(self):
        return f"{self.guardian} → {self.student}"
