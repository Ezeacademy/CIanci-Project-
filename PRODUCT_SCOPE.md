# Contrato de producto — alcance propuesto del MVP v0.3

**Estado:** Borrador. Ninguna función se considera contractual con Cianci hasta validar `DISCOVERY.md`.

## Objetivo verificable
Un alumno del instituto puede crear una cuenta, iniciar sesión, consultar clases y mensualidades, visualizar su vencimiento y pagar por transferencia bancaria o Mercado Pago. Administración puede registrar clases, emitir cuotas, verificar transferencias y consultar quién pagó y quién debe. La web pública permite consultar información del instituto y su calendario.

## Actores
- **Visitante:** ve información pública, disciplinas, profesores, calendario y contacto.
- **Alumno adulto:** accede a sus inscripciones, cuotas y pagos propios; reporta transferencia; inicia checkout de una deuda propia.
- **Tutor/responsable:** gestiona, tras autorización, uno o varios perfiles de menores vinculados, sus inscripciones, deudas y compras. Los menores no requieren credenciales propias en P0.
- **Administración:** Ema y Miri, con permisos separados y auditables, gestionan alumnos, clases, cuotas y validaciones. Inicialmente Django Admin para personal autorizado; panel de React queda pendiente de necesidad comprobada.
- **Profesor/a:** rol con acceso limitado a sus propias clases y horarios; la posibilidad de registrar dictado/cancelación requiere definir estados y permisos, sin acceso general a pagos ni a documentación sensible.
- **Proveedor de pagos:** plataforma externa que informa eventos de cobro; no es una identidad del instituto.

## Dentro del MVP obligatorio (P0)
1. Sitio institucional adaptable a celular; calendario de clases/eventos (contenido cargado por administración).
2. Alta/inicio/cierre de sesión de alumnos; recuperar acceso; permisos con deny-by-default.
3. Catálogo de disciplinas, horarios semanales e inscripciones múltiples: un alumno puede cursar varias disciplinas; alta y asociación por administración inicialmente. Los horarios recurrentes se asocian directamente a cada disciplina y pueden tener distintos profesores. El calendario privado muestra horarios activos a alumnos y tutores autorizados a partir de inscripciones vigentes; no confirma que una clase se dicte en una fecha concreta. Disciplinas y profesores pueden desactivarse sin eliminar sus relaciones históricas. Grupos o turnos independientes quedan como evolución futura; calendario de eventos, suspensiones y reprogramaciones requiere reglas posteriores.
4. Vista privada de cuotas por alumno (o tutor vinculado): concepto, período, importe aplicado, descuento/ajuste, recargo de mora cuando corresponda, fecha de vencimiento, estado e historial. Tarifas gestionables por personal autorizado con vigencia e historial; descuentos o ajustes manuales autorizados y auditados. Los ajustes posteriores conservan el cargo emitido y los pagos; cualquier excedente queda como crédito del alumno. La aplicación o devolución de créditos depende de BILLING-03B y permanece pendiente. Mora existe como regla de negocio, pero fechas, porcentajes, topes y excepciones siguen PENDIENTES; no implementar fórmulas arbitrarias. El vencimiento propuesto es el último día calendario del mes (confirmar excepciones). Cuotas históricas no cambian al editar precios vigentes.
5. Transferencia: datos bancarios de la titular, referencia/instrucción de pago, carga de comprobante y verificación manual administrativa contra movimiento bancario real. Informe detallado con fecha informada, fecha confirmada, titular/comprobante, referencia, monto, estado, quién confirmó y relación con cuota/alumno.
6. Mercado Pago (Checkout Pro), en ambiente de prueba antes de producción, con confirmación servidor-a-servidor validada, persistencia e idempotencia de eventos.
7. Django Admin para gestión por Ema y Miri con privilegios mínimos, auditoría de ajustes y pagos, backups y configuración segura de producción.
8. Acceso restringido por deuda, sujeto a definición administrativa: mantener siempre autenticación, pantalla de deudas/pago, recibos y canal de soporte; restringir solo funciones aprobadas y contemplar pagos en revisión/errores/gracia. No bloquear login.
9. Constancia interna digital verificable para pagos confirmados: identificador no predecible, fecha, alumno/concepto/monto, estado y URL/QR de verificación con comprobación de permisos y posibilidad de anulación; no afirmar que un PDF o QR sea imposible de copiar ni que reemplace una factura fiscal.
10. Datos mínimos para la operación: identidad/contacto/DNI y fecha de nacimiento SOLO donde se justifique y con medidas de privacidad. Datos médicos/condiciones de salud NO se recopilan ni modelan en P0 hasta resolver necesidad, base legal, protección y permisos específicos.
11. API REST versionada y documentada; tests de permisos y reglas críticas; frontend Next.js separado.

## Fuera del MVP obligatorio (P1/P2)
- Ticketing básico P1: una vez aprobado P0, publicar función, cupos generales, compra de entradas SOLO con login (alumnos adultos o tutores autorizados), emisión/validación de QR y pantalla tipo ticketera SIN mapa de butacas ni selección de asientos.
- Ticketing de butacas P2: planos de teatros, asientos numerados, reservas temporales, concurrencia y actualización en vivo.
- React Native, múltiples institutos, estadísticas avanzadas, débitos automáticos, integraciones contables, notificaciones masivas, soporte 24/7, motor complejo de promociones/cupones, autoservicio de cambios de clase. Ajustes manuales y descuentos simples autorizados SÍ entran en cuotas P0.
- Automatización de transferencias bancarias P2: requiere proveedor y acuerdos específicos, NO se supone disponible mediante un simple alias/QR.

## Flujos y aceptación del MVP
### CU-01 Acceso
Dado un alumno registrado, puede entrar y ver solo sus datos. Un alumno A no puede acceder a mensualidad B cambiando el ID en URL o API. Administración sí puede administrar según permisos.

### CU-02 Mensualidad
Administración crea o genera una cuota según reglas del instituto. El alumno ve monto y vencimiento. El importe y estado no se definen en el frontend. No hay doble cuota para mismo alumno + período + concepto, salvo regla explícita.

### CU-03 Transferencia
El alumno ve datos de la cuenta receptora, inicia una transferencia externa y opcionalmente adjunta referencia/comprobante. El estado es «en revisión», nunca «pagado» por subir un archivo. Administración verifica ingreso efectivo, confirma una sola vez y queda registro de quién aprobó y cuándo. Denegación/corrección por proceso autorizado.

### CU-04 Mercado Pago
El backend calcula monto y genera operación; un webhook validado desencadena consulta/verificación de estado ante proveedor. Notificaciones duplicadas, fuera de orden o reintentadas nunca duplican pagos ni emiten doble recibo. Un rechazo no marca cuota pagada. Reembolsos tienen política pendiente.

### CU-05 Sitio público
Contenido básico navegable desde celular, sin login obligatorio para calendario público; no expone información de alumnos ni medios de pago privados.

## Límites comerciales y operativos
- El costo de infraestructura, dominio y comisiones se cotiza aparte del desarrollo.
- Alcance de mantenimiento separado del desarrollo y limitado por horas/tareas acordadas.
- Recargos/descuentos por medio de pago, titularidad de cuenta y comprobantes/facturación necesitan validación comercial/contable/legal; no implementarlos como decisión tomada.
- El instituto es propietario de sus datos y debe disponer de exportación/acceso según contrato. Reutilización de software genérico depende del acuerdo de propiedad intelectual.
- La plataforma no guardará datos de tarjeta bancaria. Minimizar datos personales y tratamiento especial de menores.

## Condición de congelamiento del alcance
Nada «implícito» entra en P0. Solicitudes adicionales van a backlog con prioridad, costo, impacto y decisión explícita. P1 comienza solo después de aceptar P0.

## Decisiones registradas el 24/10/2026 (usuario/desarrollador)
- Una persona/alumno puede inscribirse a varias disciplinas y mantener su historial por curso.
- Las tarifas base pueden variar; descuentos o promociones simples deben quedar reflejados por cuota y auditados. No se modelará un sistema de reglas promocionales general.
- El vencimiento general será el último día calendario de cada mes; falta validar política ante ingresos a mitad de mes, feriados y atrasos.
- Se prefiere que adultos tutores controlen perfiles de alumnos menores; definir más adelante datos exigidos, consentimiento, autorización para visualizar información y cambios de custodia.
- Se requiere trazabilidad detallada de transferencias, diferenciando **declaración** del alumno de **acreditación** verificada.
- El ticketing P1 se limita a usuarios autenticados y cupos generales; interfaz visual agradable tipo boletería, NO un plano de butacas.
- No confundir Mercado Pago/Stripe con acceso a movimientos de una cuenta bancaria privada; automatización de conciliación bancaria requiere acceso autorizado a proveedor bancario/PSP concreto. Stripe Payments no está disponible para alta directa en Argentina según lista oficial actual.

## Casos de aceptación adicionales
- Alumno con dos inscripciones ve ambas y los conceptos correspondientes sin generar cargos duplicados.
- Un tutor puede ver información únicamente de menores vinculados explícitamente; no puede consultar otro alumno usando IDs arbitrarios.
- Cambiar precio de una disciplina NO reescribe importes históricos de cuotas ya emitidas.
- Descuento manual autorizado guarda: valor/tipo, motivo, responsable, fecha y total resultante; importes nunca dependen del cliente.
- El sistema distingue fecha de presentación del comprobante de fecha real acreditada; no marca pagado por cargar archivo o número de operación.
- Listado administrativo permite filtrar por alumno, período, fecha, método, estado y exportar información suficiente para conciliación manual; no presenta comprobante como transacción confirmada.

## Decisiones adicionales registradas el 24/10/2026 (sujetas a campo)
- Confirmado por desarrollador: hay múltiples danzas, pueden discontinuarse/reactivarse; los docentes pueden cambiar sin perder historial.
- Confirmado como requisito: administración autorizada modifica precios; hay mora escalonada (se menciona un tramo días 1–10, fórmula concreta NO CONFIRMADA). Ema debe aportar ejemplos.
- Confirmado como requisito: usuarios con mensualidad adeudada deben tener funcionalidad limitada. DEFINIR funciones, tolerancias y excepciones; login y canal de pago SIEMPRE disponibles.
- Confirmado como requisito: nuevo rol profesor, calendario unificado y novedades de dictado de clases. Estados y permisos específicos pendientes.
- Miri Cianci figura como titular prevista de la cuenta receptora; alias, CBU/CVU, cuenta técnica de Mercado Pago y datos de contacto pendientes. NO inventar ni fijar credenciales en código o documentos.
- El instituto dispone de logo/colores y dirección/contactos por incorporar con materiales autorizados. Dominio aún no registrado.
- Solicitud de registrar nombre, fecha de nacimiento, DNI y teléfono: evaluar finalidad y minimización. Solicitud de guardar información de salud: REQUIERE evaluación legal y privacidad especial; excluir por ahora.
- Constancia interna verificable de pago solicitada; formato y diferencia respecto de factura fiscal pendientes de validación con contador.
