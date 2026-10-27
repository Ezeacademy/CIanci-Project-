from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from adminpanel.permissions import INSTITUTE_ADMIN_PERMISSIONS


class Command(BaseCommand):
    help = "Create or update the Institute Administrator group permissions."

    @transaction.atomic
    def handle(self, *args, **options):
        permissions = []
        missing = []
        for permission_name in INSTITUTE_ADMIN_PERMISSIONS:
            app_label, codename = permission_name.split(".", maxsplit=1)
            permission = Permission.objects.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).first()
            if permission is None:
                missing.append(permission_name)
            else:
                permissions.append(permission)

        if missing:
            raise CommandError(
                "Faltan permisos de modelo. Aplicá primero las migraciones: "
                + ", ".join(missing)
            )

        group, created = Group.objects.get_or_create(name="Institute Administrator")
        group.permissions.set(permissions)
        action = "creado" if created else "actualizado"
        self.stdout.write(
            self.style.SUCCESS(
                f"Grupo Institute Administrator {action} con "
                f"{len(permissions)} permisos. No se asignó a usuarios."
            )
        )
