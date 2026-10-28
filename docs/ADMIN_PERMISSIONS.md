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

No se conceden permisos `delete_*`, permisos de aplicación o devolución de créditos, permisos de escritura de tarifas ni permisos `accounts.*user`, `auth.*group` o `auth.*permission`. La administración general de usuarios y credenciales queda fuera del grupo; las únicas operaciones relacionadas con cuentas son las invitaciones y revocaciones académicas limitadas descritas abajo. El campo directo `Student.user` de Django Admin queda reservado a superusuarios para impedir que `academy.change_student` omita el flujo de invitación. Las futuras capacidades de tarifas pueden añadirse al grupo cuando una historia las autorice.

## Acceso al panel y permisos de Django

- `is_staff` permite iniciar sesión en Django Admin. Por sí solo no concede operaciones del instituto.
- `is_superuser` omite las comprobaciones habituales de permisos de Django. Se reserva al desarrollador y no debe asignarse a Ema.
- Los permisos de modelo (`view`, `add`, `change`) habilitan operaciones concretas. Los servicios económicos conservan sus propios chequeos de permisos.
- Los grupos reúnen permisos reutilizables. Un usuario también puede recibir permisos individuales, que Django combina con los permisos de sus grupos.
- El dashboard requiere una cuenta activa con `is_staff` y los permisos `academy.view_student`, `billing.view_monthlycharge`, `payments.view_paymentintent` y `academy.view_classschedule`. Los enlaces de cada operación solo aparecen con sus permisos requeridos; las pantallas también validan cada permiso en el backend.
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
3. Que el acceso a alumnos muestre solo las acciones permitidas; las operaciones que aún no tengan pantalla propia abran su destino autorizado de Django Admin.
4. Que un usuario autenticado sin el conjunto de permisos reciba `403` del endpoint `/api/v1/admin-panel/dashboard`.
5. Que al retirar un permiso requerido se pierda el acceso al endpoint; al retirar permisos operativos, Django Admin deniegue esa operación.
6. Que una persona anónima no pueda consultar el endpoint.

ADMIN-01 no asigna este grupo a Ema ni a ningún otro usuario real. El onboarding de Ema debe ser explícito y efectuado por una persona autorizada.

## Gestión académica del panel (ADMIN-02)

El panel ofrece `/admin-panel/alumnos` para el listado, búsqueda y filtros; `/admin-panel/alumnos/nuevo` para registrar; `/admin-panel/alumnos/<id>` para consultar la ficha e inscripciones; y `/admin-panel/alumnos/<id>/editar` para editar los datos personales disponibles. La API privada correspondiente vive bajo `/api/v1/admin/academic/students`.

| Permiso técnico | Operación del panel | Alcance |
|---|---|---|
| `academy.view_student` | Listar y consultar fichas de alumnos | Se combina con lectura de inscripciones y disciplinas para mostrar el estado académico. |
| `academy.add_student` | Registrar un alumno | Solo nombre, apellido y fecha de nacimiento opcional; no crea ni vincula cuentas. |
| `academy.change_student` | Editar datos personales disponibles | No modifica cuenta vinculada ni relaciones de tutoría. |
| `academy.invite_student_account` | Enviar invitación para vincular una cuenta propia | Solo crea invitaciones ligadas a un alumno existente; no crea usuarios, no asigna contraseñas y no vincula sin aceptación del destinatario verificado. |
| `academy.revoke_student_account` | Revocar el acceso de una cuenta vinculada | Desvincula el acceso actual y deja registro administrativo; conserva alumno, inscripciones, mensualidades, pagos e historial de invitación. |
| `academy.view_enrollment` | Consultar inscripciones e historial | Lectura de actividad y disciplinas asociadas. |
| `academy.add_enrollment` | Inscribir en una disciplina activa | Respeta la unicidad de inscripción activa y la regla existente de mensualidad inicial cuando el actor también tiene `billing.add_monthlycharge`. |
| `academy.change_enrollment` | Finalizar una inscripción activa | Registra la baja de hoy y conserva el historial; no reactiva inscripciones finalizadas. |
| `academy.view_discipline` | Consultar disciplinas y ofrecer filtros/selección | Las nuevas inscripciones solo aceptan disciplinas activas. |
| `accounts.view_guardianrelationship` | Consultar tutores asociados | Solo muestra nombres y vigencia del vínculo; no expone emails ni permite editarlo. |

Las operaciones de alta, edición, inscripción y finalización quedan registradas en el historial de Django Admin con el usuario responsable. Cada endpoint exige `is_staff` y el permiso Django de la operación; ocultar acciones en el frontend no sustituye esta validación. El grupo operativo no recibe permisos para crear o editar usuarios, grupos ni credenciales; los dos permisos anteriores solo permiten gestionar invitaciones y el vínculo académico.

## Vinculación de cuenta propia (ADMIN-02B)

Desde la ficha del alumno, un operador con `academy.invite_student_account` puede enviar una invitación temporal al correo ingresado. Debe verificar institucionalmente que ese correo corresponde a la persona. El token se almacena como hash y se envía por correo; no se devuelve al panel ni se registra en logs. Se mantiene una sola invitación pendiente por alumno: una invitación vigente no se reemplaza silenciosamente; una vencida se registra como reemplazada al emitir otra. El personal puede cancelar una pendiente.

Si la persona no tiene cuenta, activa la cuenta mediante el flujo existente y verifica el email. Si ya tiene cuenta, inicia sesión con ese email. En ambos casos, Mi cuenta muestra el alumno y requiere aceptación explícita. La API valida sesión, email exacto, verificación, vencimiento y estado, y realiza el vínculo en una transacción. Aceptar no crea otro alumno ni altera inscripciones o datos financieros.

Para revocar una cuenta vinculada, un operador con `academy.revoke_student_account` confirma la acción desde la ficha. Se limpia solo `Student.user`; el siguiente acceso privado deja de incluir al alumno. La invitación aceptada conserva destinatario, emisor, fecha y cuenta aceptante; el historial administrativo registra quién revocó el vínculo y cuándo. Las invitaciones para tutores y sus consentimientos no forman parte de ADMIN-02B.

Para habilitar los permisos en el grupo, aplicar las migraciones y ejecutar `python manage.py sync_institute_admin_group`. El comando actualiza la lista de permisos del grupo sin asignarlo a usuarios reales.

## Consulta de mensualidades (ADMIN-03A)

El panel ofrece `/admin-panel/mensualidades` para buscar y filtrar mensualidades y `/admin-panel/mensualidades/<id>` para consultar pagos aplicados y ajustes registrados. La API privada vive en `/api/v1/admin/billing/monthly-charges`. Ambas operaciones requieren `billing.view_monthlycharge`, `billing.view_chargeadjustment` y `payments.view_payment`; estos permisos ya están incluidos en `Institute Administrator`. Los importes se obtienen mediante `charges_with_economic_totals()` y la consulta no permite modificar cargos, pagos ni ajustes.

## Espectáculos y mapas físicos (TICKET-01)

`/admin-panel/espectaculos` administra espectáculos y funciones; `/admin-panel/recintos` permite crear recintos, y `/admin-panel/recintos/<id>` permite configurar sus mapas versionados. Las APIs privadas están bajo `/api/v1/admin/ticketing/`.

| Permiso técnico | Operación | Motivo |
|---|---|---|
| `tickets.view_show` | Consultar espectáculos, funciones, recintos y mapas | Permite revisar la programación y configuración física sin modificarlas. |
| `tickets.manage_ticketing` | Crear/editar espectáculos y recintos, versionar mapas, configurar funciones y precios por sector | Capacidad operativa necesaria para preparar eventos y sus funciones. El permiso se verifica en backend para cada escritura. |

Ambos permisos se incluyen en el grupo `Institute Administrator` cuando se ejecuta `python manage.py sync_institute_admin_group`; no se asignan a usuarios reales automáticamente. El mapa usa sectores, filas, asientos y espacios normalizados. Su capacidad se calcula contando asientos operativos. Al asociar una versión a una función, la estructura queda congelada y los cambios requieren crear una nueva versión. Los precios se guardan por función y sector, fuera del mapa. No se habilitan ventas, reservas, pagos ni QR.
