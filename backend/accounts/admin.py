from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone

from .forms import AccountChangeForm, AccountCreationForm, AccountInvitationForm
from .invitations import issue_invitation
from .models import AccountInvitation, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    ordering = ("email",)
    search_fields = ("email", "first_name", "last_name")
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Información personal", {"fields": ("first_name", "last_name")}),
        (
            "Permisos técnicos",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
    )


@admin.register(AccountInvitation)
class AccountInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "email",
        "status",
        "expires_at",
        "created_at",
        "created_by",
        "claimed_user",
    )
    list_filter = ("consumed_at", "revoked_at", "expires_at")
    search_fields = ("email", "first_name", "last_name")
    actions = ("revoke_invitations",)
    fields = (
        "email",
        "first_name",
        "last_name",
        "created_by",
        "created_at",
        "expires_at",
        "consumed_at",
        "claimed_user",
        "revoked_at",
        "revoked_by",
    )
    readonly_fields = fields

    def get_urls(self):
        custom_urls = [
            path(
                "add/",
                self.admin_site.admin_view(self.add_invitation),
                name="accounts_accountinvitation_add",
            )
        ]
        return custom_urls + super().get_urls()

    def has_delete_permission(self, request, obj=None):
        return False

    def status(self, invitation):
        if invitation.consumed_at:
            return "Usada"
        if invitation.revoked_at:
            return "Revocada"
        if invitation.expires_at <= timezone.now():
            return "Vencida"
        return "Pendiente"

    status.short_description = "Estado"

    def add_invitation(self, request):
        opts = self.model._meta
        if not self.has_add_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied

        if request.method == "POST":
            form = AccountInvitationForm(request.POST)
            if form.is_valid():
                invitation, token = issue_invitation(
                    email=form.cleaned_data["email"],
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    expires_at=form.cleaned_data["expires_at"],
                    created_by=request.user,
                )
                self.log_addition(request, invitation, "Invitación creada.")
                context = {
                    **self.admin_site.each_context(request),
                    "opts": opts,
                    "title": "Invitación creada",
                    "invitation": invitation,
                    "invitation_url": (f"{settings.FRONTEND_BASE_URL}/activar#{token}"),
                    "changelist_url": reverse(
                        "admin:accounts_accountinvitation_changelist"
                    ),
                }
                response = TemplateResponse(
                    request,
                    "admin/accounts/accountinvitation/created.html",
                    context,
                )
                response["Cache-Control"] = "no-store"
                response["Referrer-Policy"] = "no-referrer"
                return response
        else:
            form = AccountInvitationForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": opts,
            "title": "Crear invitación",
            "form": form,
            "changelist_url": reverse("admin:accounts_accountinvitation_changelist"),
        }
        response = TemplateResponse(
            request,
            "admin/accounts/accountinvitation/add_form.html",
            context,
        )
        response["Cache-Control"] = "no-store"
        return response

    @admin.action(description="Revocar invitaciones seleccionadas")
    def revoke_invitations(self, request, queryset):
        now = timezone.now()
        with transaction.atomic():
            invitations = queryset.select_for_update()
            for invitation in invitations:
                if invitation.consumed_at or invitation.revoked_at:
                    continue
                invitation.revoked_at = now
                invitation.revoked_by = request.user
                invitation.save(update_fields=("revoked_at", "revoked_by"))
                self.log_change(
                    request,
                    invitation,
                    [{"changed": {"fields": ["revoked_at"]}}],
                )
