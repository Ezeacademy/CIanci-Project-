from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import AutocompleteSelectMultiple
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.db.models import F
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext, ngettext
from django.utils.translation import gettext_lazy as _

from academy.models import Student

from .forms import AccountChangeForm, AccountCreationForm, AccountInvitationForm
from .invitations import issue_invitation
from .models import AccountInvitation, GuardianRelationship, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    add_form = AccountCreationForm
    form = AccountChangeForm
    ordering = ("email",)
    search_fields = ("email", "first_name", "last_name")
    list_display = ("email", "first_name", "last_name", "is_staff", "is_active")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Información personal"), {"fields": ("first_name", "last_name")}),
        (
            _("Permisos técnicos"),
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
        (_("Fechas"), {"fields": ("last_login", "date_joined")}),
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
            return gettext("Usada")
        if invitation.revoked_at:
            return gettext("Revocada")
        if invitation.expires_at <= timezone.now():
            return gettext("Vencida")
        return gettext("Pendiente")

    status.short_description = _("Estado")

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
                self.log_addition(request, invitation, gettext("Invitación creada."))
                context = {
                    **self.admin_site.each_context(request),
                    "opts": opts,
                    "title": _("Invitación creada"),
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
            "title": _("Crear invitación"),
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

    @admin.action(description=_("Revocar invitaciones seleccionadas"))
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


class GuardianRelationshipAdminForm(forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        label=_("Alumnos"),
        queryset=Student.objects.all(),
        widget=AutocompleteSelectMultiple(
            GuardianRelationship._meta.get_field("student"), admin.site
        ),
    )

    class Meta:
        model = GuardianRelationship
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["students"].required = False

    def clean(self):
        cleaned_data = super().clean()
        guardian = cleaned_data.get("guardian")
        students = cleaned_data.get("students")
        if guardian is None or students is None:
            return cleaned_data

        # The Admin POST is atomic. Locking the tutor row serializes concurrent
        # bulk-link submissions for that tutor before checking active links.
        guardian = User.objects.select_for_update().get(pk=guardian.pk)
        cleaned_data["guardian"] = guardian
        student_ids = list(students.values_list("pk", flat=True))
        existing_ids = set(
            GuardianRelationship.objects.filter(
                guardian=guardian,
                student_id__in=student_ids,
                revoked_at__isnull=True,
            ).values_list("student_id", flat=True)
        )
        self.new_student_ids = [
            student_id for student_id in student_ids if student_id not in existing_ids
        ]
        self.skipped_existing_count = len(student_ids) - len(self.new_student_ids)

        if not self.new_student_ids:
            if len(student_ids) == 1:
                message = _("Este tutor ya está vinculado con este alumno.")
            else:
                message = _(
                    "Todos los alumnos seleccionados ya están vinculados "
                    "con este tutor."
                )
            self.add_error("students", message)
        return cleaned_data


class GuardianRelationshipStatusFilter(admin.SimpleListFilter):
    title = _("Estado")
    parameter_name = "estado"

    def lookups(self, request, model_admin):
        return (
            ("vigente", _("Vigente")),
            ("revocado", _("Revocado")),
        )

    def queryset(self, request, queryset):
        if self.value() == "vigente":
            return queryset.filter(revoked_at__isnull=True)
        if self.value() == "revocado":
            return queryset.filter(revoked_at__isnull=False)
        return queryset


@admin.register(GuardianRelationship)
class GuardianRelationshipAdmin(admin.ModelAdmin):
    form = GuardianRelationshipAdminForm
    list_display = (
        "guardian",
        "student",
        "status",
        "created_at",
        "created_by",
        "revoked_at",
        "revoked_by",
    )
    list_filter = (GuardianRelationshipStatusFilter, "created_at")
    ordering = (
        F("revoked_at").asc(nulls_first=True),
        "student__last_name",
        "student__first_name",
        "guardian__email",
        "created_at",
    )
    search_fields = (
        "guardian__email",
        "guardian__first_name",
        "guardian__last_name",
        "student__first_name",
        "student__last_name",
    )
    autocomplete_fields = ("guardian",)
    actions = ("revoke_relationships",)
    fields = (
        "guardian",
        "student",
        "created_at",
        "created_by",
        "revoked_at",
        "revoked_by",
    )

    @admin.display(description=_("Estado"), ordering="revoked_at")
    def status(self, relationship):
        return _("Revocado") if relationship.revoked_at else _("Vigente")

    def get_readonly_fields(self, request, obj=None):
        readonly = ("created_at", "created_by", "revoked_at", "revoked_by")
        if obj:
            return self.fields
        return readonly

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return ((None, {"fields": ("guardian", "students")}),)
        return super().get_fieldsets(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.student_id = form.new_student_ids[0]
            obj.guardian = form.cleaned_data["guardian"]
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        if not change and len(form.new_student_ids) > 1:
            GuardianRelationship.objects.bulk_create(
                [
                    GuardianRelationship(
                        guardian_id=obj.guardian_id,
                        student_id=student_id,
                        created_by=request.user,
                    )
                    for student_id in form.new_student_ids[1:]
                ]
            )
            obj._bulk_created_count = len(form.new_student_ids)
        elif not change:
            obj._bulk_created_count = 1
        if not change:
            obj._bulk_skipped_count = form.skipped_existing_count

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue)
        created = getattr(obj, "_bulk_created_count", 1)
        skipped = getattr(obj, "_bulk_skipped_count", 0)
        if created > 1 or skipped:
            message = ngettext(
                "Se creó %(count)d vínculo vigente.",
                "Se crearon %(count)d vínculos vigentes.",
                created,
            ) % {"count": created}
            if skipped:
                message += " " + ngettext(
                    "Se omitió %(count)d vínculo que ya existía.",
                    "Se omitieron %(count)d vínculos que ya existían.",
                    skipped,
                ) % {"count": skipped}
            self.message_user(request, message, messages.SUCCESS)
        return response

    @admin.action(description=_("Desvincular tutores seleccionados"))
    def revoke_relationships(self, request, queryset):
        with transaction.atomic():
            relationships = queryset.select_for_update().filter(revoked_at__isnull=True)
            for relationship in relationships:
                relationship.revoked_at = timezone.now()
                relationship.revoked_by = request.user
                relationship.save(update_fields=("revoked_at", "revoked_by"))
                self.log_change(
                    request,
                    relationship,
                    [{"changed": {"fields": ["revoked_at", "revoked_by"]}}],
                )
