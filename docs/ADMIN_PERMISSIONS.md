# Permisos del panel administrativo

## Roles y alcance

El grupo `Institute Administrator` reúne permisos operativos de Ema. El grupo no se asigna automáticamente a ninguna cuenta. ADMIN-01 conserva los servicios y validaciones existentes para ajustes, pagos, transferencias e inscripciones.

| Permiso técnico | Operación habilitada | Motivo operativo |
|---|---|---|
| `accounts.view_guardianrelationship` | Consultar vínculos entre tutores y alumnos | Resolver consultas administrativas sobre quién está autorizado a acompañar a cada menor. |
| `academy.view_student`, `academy.add_student`, `academy.change_student` | Consultar, registrar y corregir datos de alumnos | Mantener actualizado el registro académico cotidiano. |
| `academy.view_enrollment`, `academy.add_enrollment`, `academy.change_enrollment` | Consultar, crear y finalizar inscripciones | Registrar altas y bajas mediante las validaciones actuales. |
| `academy.view_discipline`, `academy.add_discipline`, `academy.change_discipline` | Consultar y administrar disciplinas | Mantener la oferta del instituto. |
| `academy.view_teacher`, `academy.add_teacher`, `academy.change_teacher` | Consultar y administrar profesores | Mantener la nómina docente y su estado. |
| `academy.view_classschedule`, `academy.add_classschedule`, `academy.change_classschedule` | Consultar y administrar horarios semanales | Mantener los horarios recurrentes publicados a alumnos. |
| `billing.view_disciplineprice` | Consultar tarifas | La pantalla existente de generación informa precios aplicables y disciplinas sin tarifa. |
| `billing.view_monthlycharge` | Consultar mensualidades, pagos aplicados y saldos | Responder consultas de cobro sin recalcular importes en el panel. |
| `billing.add_monthlycharge` | Abrir la generación existente de mensualidades | Django Admin usa este permiso para la operación; no permite crear cargos manualmente. |
| `billing.view_chargeadjustment`, `billing.adjust_monthlycharge` | Consultar el historial y ajustar mensualidades | Registrar correcciones económicas con el servicio auditado existente. |
| `payments.view_payment`, `payments.add_payment` | Consultar pagos y registrar efectivo | Registrar dinero recibido con las asignaciones y validaciones existentes. |
| `payments.view_paymentintent`, `payments.change_paymentintent` | Consultar, confirmar y rechazar transferencias pendientes | Revisar el dinero informado y dejar constancia de quién lo resolvió. |
| `payments.view_creditrelease` | Consultar saldos a favor generados | Ver excedentes liberados por correcciones auditadas. No permite aplicarlos ni devolverlos. |

No se conceden permisos `delete_*`, permisos de aplicación o devolución de créditos, permisos de escritura de tarifas ni permisos `accounts.*user`, `auth.*group` o `auth.*permission`. La administración de usuarios y cuentas asociadas a alumnos queda fuera de este grupo. Las futuras capacidades de tarifas pueden añadirse al grupo cuando una historia las autorice.

## Acceso al panel y permisos de Django

- `is_staff` permite iniciar sesión en Django Admin. Por sí solo no concede operaciones del instituto.
- `is_superuser` omite las comprobaciones habituales de permisos de Django. Se reserva al desarrollador y no debe asignarse a Ema.
- Los permisos de modelo (`view`, `add`, `change`) habilitan operaciones concretas. Los servicios económicos conservan sus propios chequeos de permisos.
- Los grupos reúnen permisos reutilizables. Un usuario también puede recibir permisos individuales, que Django combina con los permisos de sus grupos.
- El dashboard requiere una cuenta activa con `is_staff` y los permisos `academy.view_student`, `billing.view_monthlycharge`, `payments.view_paymentintent` y `academy.view_classschedule`. Cada enlace a Django Admin requiere además el permiso propio de esa operación.
- El usuario desarrollador conserva sus permisos existentes; esta configuración no modifica cuentas reales.

## Crear o actualizar el grupo

Después de aplicar las migraciones del proyecto, ejecutar:

```sh
python manage.py sync_institute_admin_group
```

El comando es idempotente: crea o actualiza `Institute Administrator` con la lista exacta documentada en `adminpanel.permissions.INSTITUTE_ADMIN_PERMISSIONS`. No asigna el grupo a usuarios. Si se modifica la lista de permisos aprobada, volver a ejecutar el comando.

## Asignar y retirar el grupo desde Django Shell

Primero, un operador autorizado debe marcar la cuenta como activa y `is_staff=True` para permitir su acceso a Django Admin; ese cambio es independiente de asignar permisos:

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()
user = User.objects.get(pk=USER_ID)
user.is_active = True
user.is_staff = True
user.save(update_fields=["is_active", "is_staff"])
user.groups.add(Group.objects.get(name="Institute Administrator"))
```

Retirar el grupo:

```python
user.groups.remove(Group.objects.get(name="Institute Administrator"))
```

No cambiar `is_staff` al retirar el grupo si la persona todavía necesita otros accesos autorizados a Django Admin. Si no los necesita, un operador puede quitarlo por separado. Nunca modificar `is_superuser` como parte de este flujo.

## Consultar permisos efectivos

```python
user.get_group_permissions()
user.get_user_permissions()
user.get_all_permissions()
user.has_perm("billing.adjust_monthlycharge")
user.is_staff, user.is_superuser, user.is_active
```

Para comprobar revocación, quitar el grupo o permiso individual y repetir `get_all_permissions()` / `has_perm()`. El dashboard también rechaza solicitudes directas al endpoint si faltan sus permisos requeridos; ocultar un enlace en la web no es la protección.

## Prueba con administrador no superusuario

En un entorno local, usar una cuenta de prueba que no sea superusuario. Asignarle el grupo con el procedimiento anterior, iniciar sesión y comprobar:

1. `is_staff=True`, `is_superuser=False` y acceso a `/admin-panel`.
2. Que el dashboard muestre datos reales y sus respuestas no se almacenen en caché.
3. Que cada enlace abra la operación permitida de Django Admin.
4. Que un usuario autenticado sin el conjunto de permisos reciba `403` del endpoint `/api/v1/admin-panel/dashboard`.
5. Que al retirar un permiso requerido se pierda el acceso al endpoint; al retirar permisos operativos, Django Admin deniegue esa operación.
6. Que una persona anónima no pueda consultar el endpoint.

ADMIN-01 no asigna este grupo a Ema ni a ningún otro usuario real. El onboarding de Ema debe ser explícito y efectuado por una persona autorizada.
