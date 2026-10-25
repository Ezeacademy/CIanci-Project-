from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import User


class AccountCreationForm(BaseUserCreationForm):
    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {}


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        field_classes = {}
