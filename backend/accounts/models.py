from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField("email", unique=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta(AbstractUser.Meta):
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
                type(self).objects.filter(pk=self.pk)
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
    token_hash = models.CharField(max_length=64, unique=True)
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_account_invitations",
    )
    claimed_user = models.OneToOneField(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="account_invitation",
    )
    revoked_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="revoked_account_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(consumed_at__isnull=True)
                | models.Q(revoked_at__isnull=True),
                name="accounts_invite_not_consumed_and_revoked",
            ),
            models.CheckConstraint(
                condition=models.Q(consumed_at__isnull=True)
                | models.Q(claimed_user__isnull=False),
                name="accounts_invite_consumed_has_user",
            ),
        ]
        ordering = ("-created_at",)

    def __str__(self):
        return self.email or f"Invitación {self.pk}"
