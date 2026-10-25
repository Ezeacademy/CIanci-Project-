from django import forms
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm
from django.utils import timezone

from .models import AccountInvitation, User


class AccountCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {}


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        field_classes = {}


class AccountInvitationForm(forms.ModelForm):
    expires_at = forms.DateTimeField(
        input_formats=("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"),
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )

    class Meta:
        model = AccountInvitation
        fields = ("email", "first_name", "last_name", "expires_at")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        return User.objects.normalize_email(email) if email else None

    def clean_expires_at(self):
        expires_at = self.cleaned_data["expires_at"]
        if expires_at <= timezone.now():
            raise forms.ValidationError("La invitación debe vencer en el futuro.")
        return expires_at
