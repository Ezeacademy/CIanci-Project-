# Contrato de arquitectura — propuesta v0.3

## Forma del sistema
- **Monorepo:** `backend/` (Django + DRF), `frontend/` (Next.js App Router + React + TypeScript + Tailwind), `docs/`, `compose.yaml`, workflows de CI.
- **Backend:** un monolito modular, un despliegue Python, una base PostgreSQL. No es una malla de servicios.
- **Frontend:** aplicación Next.js desplegable por separado; consume contratos `/api/v1/` de Django. Ni React ni Route Handlers de Next son autoridad sobre precios, vencimientos, permisos o pagos.
- **Gestión:** el panel Next.js ofrece el dashboard operativo de ADMIN-01 y, desde ADMIN-02, la gestión de alumnos e inscripciones con endpoints privados de `academy`. Django Admin conserva las demás operaciones administrativas y permanece disponible para personal autorizado.
- **Externos:** Mercado Pago; cuenta bancaria de recepción a nombre de la persona/instituto correspondiente; DNS/dominio y hosting a definir en fase de despliegue.

## Ownership de módulos Django
| Módulo | Dueño de | NO dueño de |
|---|---|---|
| `accounts` | cuentas, autenticación, invitaciones de cuenta y acceso académico, vínculos autorizados de tutores con menores | deudas, cobros |
| `academy` | disciplinas, clases, horarios, profesores, relación con docentes y fechas de asignación, inscripciones (alumno puede tener varias), novedades de clase | estado de pago |
| `billing` | tarifa base con vigencias, emisión de cuotas, importes aplicados (snapshot), descuentos/ajustes, reglas de mora aprobadas, vencimientos, deuda y elegibilidad por pago | transacción con PSP |
| `payments` | operaciones, evidencias bancarias, proveedor, webhooks, conciliación, auditoría y constancias verificables sobre pagos confirmados | precio de la cuota y regla de mora |
| `tickets` | espectáculos, funciones, recintos y versiones normalizadas de mapas físicos | ventas, pagos y gestión de clases |
| `core` | configuración compartida mínima, sin lógica de dominio | vertedero de helpers |

**Criterio:** los modelos y reglas viven en su módulo dueño. Integración entre módulos a través de operaciones explícitas y comprobables; import directo entre modelos solo cuando justificado por una relación del dominio, sin imports circulares. No duplicar tablas ni reglas para «aislar» artificialmente un monolito.

**Ajustes y créditos (BILLING-03):** `billing` conserva el cargo original y registra ajustes acumulativos auditados; `payments` conserva pagos y asignaciones originales y registra el excedente liberado como crédito vinculado a su asignación de origen. BILLING-03A expone deuda y créditos disponibles; aplicar o devolver esos créditos requiere BILLING-03B.

## Capas pragmáticas
- View/Serializer: protocolo HTTP, entrada y salida, no lógica compleja.
- Model + manager/queryset: esquema, invariantes y consultas simples de Django ORM.
- Servicios de casos de uso: para operaciones transaccionales o coordinación relevante (por ejemplo confirmar un pago); no un service obligatorio por cada tabla.
- Adaptadores de integraciones: frontera externa en `payments/integrations/`.
- Abstracción y DTO solo si hay al menos una necesidad concreta, no como «boilerplate enterprise».

## API y autenticación
- Definir contrato HTTP OpenAPI con DRF, convención consistente de recursos, paginación, errores y versionado `/api/v1`.
- Política de autenticación web **pendiente de spike**: favorecer sesiones Django seguras con cookies HttpOnly, Secure y protección CSRF, verificando el flujo real SSR Next.js + subdominios + CORS. No usar JWT/almacenamiento local por reflejo. El futuro móvil podrá usar una estrategia adecuada sin reinventar el backend.
- Autorización backend por acción y objeto; el filtrado de queryset también limita lectura/listados. El frontend no decide permisos definitivos.
- Datos privados del alumno no se cachean como contenido público ni se mezclan entre usuarios en SSR.

## Persistencia y consistencia
- PostgreSQL como fuente única. Dinero: `Decimal` con precisión definida o enteros de menor denominación; jamás `float`. Moneda ARS explícita y política de redondeo definida.
- Restricciones de unicidad y de checks para proteger invariantes (p. ej. unicidad de cuota por alumno/período/concepto según negocio).
- Transacciones `atomic` cortas en cambios que deban ocurrir juntos; `select_for_update` solo en conflictos concurrentes reales. No mantener transacción abierta durante HTTP externo.
- Correlation/reference del PSP única e idempotencia en recepción de webhooks; verificar firma, titularidad, operación, moneda, monto y estado remoto antes de marcar pago.
- Comprobante no equivale a acreditación. Guardar auditoría mínima de aprobaciones/reversiones.
- Índices según consultas y EXPLAIN, no crear índices «por si acaso».

## Frontend y rendimiento
- `app/` para rutas/layouts, `features/` para componentes/casos de UI por dominio, `components/ui/` para UI reutilizable, `lib/api/` para cliente y contratos.
- Server Components por defecto; `use client` en los límites interactivos. No replicar business rules en zod/client, solo validaciones UX compatibles con API.
- Keys estables provenientes de IDs; prohibido usar índices o `Math.random()` como key en listas dinámicas.
- Estado local primero. Evitar renders encadenados por Effects; no sincronizar estado derivable; elegir una estrategia coherente de fetch y caching sin duplicar SSR y cliente innecesariamente.
- No añadir memoización/caché global sin perfil/problema de rendimiento. Usar herramientas nativas de Next (rendering/streaming) cuando tengan una utilidad concreta.
- ESLint, TypeScript `strict`, Prettier; UX responsive, accesibilidad básica, mensajes y formularios consistentes.

## Infraestructura y evolución
- Local: Docker Compose con frontend, backend y PostgreSQL (no montar Nginx/Redis solo por práctica).
- Producción tentativa: Render para API/PostgreSQL y Render/Vercel de pago según presupuesto y necesidades; confirmar costos y backup antes de aprobar.
- TLS gestionado por plataforma, dominios por DNS. Nginx solo si al migrar infraestructura aporta una función real.
- Config separada dev/test/prod, secretos por variables protegidas, backups verificables, logging mínimo y healthcheck.
- Versiones de Python, Django, Node, Next, PG y dependencias se fijan en fase base según compatibilidad oficial y soporte vigente.

## Reglas de cambio arquitectónico
Cualquier dependencia o capa nueva exige respuesta escrita a: «Qué problema actual resuelve», «Alternativa más sencilla», «Costo operativo», «Prueba o dato que demuestra el beneficio». Si no existe respuesta clara, posponer.

## Referencias oficiales
- Next Server/Client: https://nextjs.org/docs/app/getting-started/server-and-client-components
- React memo y keys: https://react.dev/reference/react/memo y https://react.dev/learn/rendering-lists
- Django atomic: https://docs.djangoproject.com/en/5.2/topics/db/transactions/
- Django optimización: https://docs.djangoproject.com/en/5.2/topics/db/optimization/
- DRF permisos: https://www.django-rest-framework.org/api-guide/permissions/
- OWASP API: https://owasp.org/API-Security/
- MP webhooks: https://www.mercadopago.com.ar/developers/es/docs/checkout-pro-orders/notifications

## Relaciones de dominio propuestas (NO son migraciones aprobadas)
- `User`: identidad autenticada de alumno adulto, tutor o personal.
- `StudentProfile`: persona estudiante, opcionalmente sin credenciales propias para menores; un `User` adulto puede vincularse al perfil que le corresponde.
- `GuardianRelationship`: vínculo explícito tutor ↔ menor, con fecha, estado y permiso verificable.
- `Discipline` / `ClassSession` / `Enrollment`: disciplinas, clases e inscripciones; relación muchos-a-muchos entre alumnos y disciplinas mediante inscripciones históricas.
- `PricePlan` o tarifa vigente en `billing` (elegir después de ver reglas reales); `MonthlyFee` mantiene copia inmutable/controlada de monto base aplicado, ajuste/descuento, total, período y vencimiento.
- `Payment`: operación que se intenta cobrar/recibir; `PaymentEvidence` (si hace falta) para comprobantes; auditoría para conciliación y estados. No identificar operación bancaria real solo con imagen o relato.
- TICKET-01 usa entidades normalizadas para `Show`, `ShowFunction`, `Venue`, `SeatMapVersion`, sectores, filas, asientos y precios por función/sector. Cada función fija una versión de mapa; la capacidad deriva de los asientos operativos. No representa reservas ni disponibilidad comercial.
- El producto continúa siendo single-institute por instalación. Una evolución multi-institute requiere una decisión arquitectónica y una historia aprobada.

## Regla bancaria y de pagos
- Mercado Pago: eventos enviados por su propia integración y validados server-to-server. También registrar estado, referencia, monto bruto/neto y comisión de proveedor cuando esté disponible para informar resultados.
- Transferencias a cuenta bancaria personal: sin API bancaria/PSP autorizado, validación MANUAL mediante movimiento real; no existe webhook universal para alias/CBU. Separar fecha declarada de fecha acreditada y guardar quién confirmó.
- No integrar Stripe para un comercio argentino sin comprobar disponibilidad/legalidad de alta del comercio; no aporta acceso mágico a movimientos bancarios.
- Reportes P0: filtro por alumno, período, canal de cobro, estado, fechas declaradas/confirmadas y referencias; exportación CSV administrativa sin exponer información de menores ni documentos a terceros.

## Conciliación y seguridad en historial
- Cuotas emitidas retienen precios originales aunque cambie un catálogo; ajustes posteriores registrados explícitamente, nunca UPDATE silencioso en pagos históricos.
- Invariantes de idempotencia en aplicación y DB (identificador externo único cuando existe, procesamiento repetible sin aplicar cuotas dos veces).
- Comprobantes almacenados fuera de directorios públicos, con permisos, validación de tamaño/tipo y acceso autorizado. Auditoría de quién y cuándo confirmó/rechazó.

## Política sobre cambios de disciplinas, docentes y horarios (v0.3)
- Desactivar o reactivar `Discipline` por estado; no borrar físicamente una disciplina con historia de alumnos/cuotas/clases. Soft-delete genérico **NO** requerido.
- Los horarios recurrentes semanales se asocian directamente a `Discipline` mediante `ClassSchedule`; una disciplina puede tener varios horarios y cada horario referencia un `Teacher`. No hay grupos o turnos independientes en esta etapa.
- `Teacher` no requiere cuenta de autenticación. Desactivar un profesor conserva sus horarios históricos, pero sus horarios activos dejan de mostrarse en el calendario privado.
- El calendario privado deriva las disciplinas de las inscripciones vigentes y muestra horarios recurrentes en la zona horaria configurada. No representa confirmación de una clase en una fecha concreta.
- Las invitaciones académicas apuntan a un `Student` existente. Solo una sesión del email destinatario, verificado y con aceptación explícita, puede asignar `Student.user`; el historial de invitación registra emisor, destinatario, alumno, aceptación y cancelación. Las invitaciones comunes conservan su activación actual.
- Grupos o turnos independientes pueden incorporarse en una historia futura si la operación lo requiere.
- Calendario unificado para sesiones regulares, feriados, ensayos y eventos, cuando sean confirmados; modelo de cancelación/reprogramación aún pendiente.
- Rol profesor con permisos por objeto asignado. No puede cambiar montos, confirmar pagos ni consultar información médica.
- Ema y Miri podrán gestionar precios desde Django Admin con permisos mínimos; evaluar interfaz administrativa Next solo tras observar inconvenientes reales.

## Mora, acceso y recibos (v0.3)
- `billing` es autoridad de vigencia de precios, recargos y elegibilidad. Una regla de mora deberá tener vigencia, tramo temporal, porcentaje/importe, exenciones y trazabilidad; no codificar días 1–10 como condición fija hasta confirmación de Ema.
- Restringir funciones por deuda mediante permisos backend por caso de uso; **nunca** denegar login, consulta de deuda, forma de pago, soporte y consulta de constancias propias. Pagos pendientes de conciliación requieren una política explícita.
- Constancia interna emitida solo tras confirmar acreditación: identificador aleatorio único, entidad origen, importe/concepto, fecha, estado vigente y verificación server-side. Una captura/PDF/QR puede copiarse; la autenticidad se comprueba en backend y puede revocarse/corregirse con auditoría. La constancia NO sustituye factura fiscal si corresponde.
- Diferenciar `payment_attempt`/evento externo, pago acreditado, imputación a cuota y constancia. Evitar duplicaciones por webhooks reintentados; DB constraints y `atomic()` cortas donde hagan falta.
- Sin colas o WebSockets por defecto: el webhook llega de Mercado Pago a Django; un estado pendiente se actualiza en el navegador por refetch/polling acotado, si hay necesidad de UX.

## Política sobre datos personales y menores
- Datos de alumnos propuestos: nombre, fecha de nacimiento, DNI y teléfono **cuando su finalidad sea necesaria**. Definir responsables, acceso, plazo de retención, consentimiento/información y exportación/eliminación con dirección y asesoría.
- Datos de salud de alumnos son sensibles en Argentina: **NO** crear campo `medical_conditions` ni colecciones de diagnósticos en P0 sin decisión expresa sobre necesidad, fundamento jurídico y diseño de resguardo. Preferir la alternativa de menor exposición y revisar con asesoría legal antes de programar.
- No exponer DNI completo en listados públicos, logs ni recibos compartibles. Limitar acceso de profesores a lo estrictamente operativo y autorizado. Mayor protección para menores y tutores.

## Pagos externos y datos bancarios
- No confundir Stripe con Mercado Pago. Webhook de PSP confirma únicamente operaciones de ese PSP. Para transferencias a Galicia/u otro banco vía alias personal de Miri se requiere conciliación real con sus movimientos o una integración bancaria/PSP autorizada.
- Alias y datos de la cuenta receptora se ingresarán mediante configuración autorizada antes del despliegue; NO inventar, compartir credenciales ni habilitar pagos reales durante prototipado.
