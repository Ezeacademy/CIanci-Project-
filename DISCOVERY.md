# Estudio de campo — preguntas para hablar con el instituto

**Propósito:** no diseñar procesos inventados. Registrá una respuesta por pregunta, quién decide y ejemplos reales (sin compartir información personal de alumnos).

## 1. Operación y tamaño
1. ¿Cuántos alumnos activos hay hoy? ¿Cuántas clases/profesores? **CONFIRMADO:** un alumno cursa varias disciplinas.
2. ¿Cómo dan de alta actualmente a un alumno? ¿Planilla, cuaderno, WhatsApp, sistema?
3. ¿Quién administra cobros y horarios? ¿Cuántas personas necesitarán acceso y con qué permisos?
4. **PROPUESTA A VALIDAR:** tutores/padres administran perfiles de menores. ¿Cómo se validan sus vínculos, quién recibe comunicaciones y cómo se revoca acceso?

## 2. Cuotas y reglas
5. **CONFIRMADO:** precio base usualmente fijo, con cambios y descuentos. **PENDIENTE:** tarifa por disciplina, plan o combinación; becas, hermanos, pagos parciales y ejemplos reales de descuentos.
6. **PROPUESTA:** vencimiento fin de mes (último día calendario). **PENDIENTE:** prorrateo de altas a mitad de mes, excepciones, mora, cuotas anteriores y ajuste de precios ya emitidos.
7. **CONFIRMADO requisito:** restringir funcionalidades a quien no haya abonado. **PENDIENTE con Ema:** qué pantallas/acciones, cuándo se bloquean, gracia y exenciones. Nunca bloquear login, consulta de deuda ni pago.
8. ¿Cómo se identifica una transferencia recibida? ¿Piden comprobante, referencia, nombre y apellido? ¿Quién reconcilia? ¿Se necesitan recibos/facturas?
9. **INDICADO por desarrollador:** cuenta bancaria a nombre de Miri Cianci. **PENDIENTE:** banco, alias/CBU, titularidad exacta, cuenta de Mercado Pago, comisiones/recargos y encuadre contable/legal. No inventar ni publicar datos de cuenta.

## 3. Calendario y eventos
10. **REQUISITO propuesto:** calendario con clases, horarios y eventos; profesores pueden reportar si se dicta una clase. **PENDIENTE:** cómo confirmar/cancelar/reprogramar, quién publica y cómo se audita.
11. **CONFIRMADO:** boletos P1 con cupo general y apariencia de ticketera; SIN butacas numeradas ni mapa interactivo. ¿Cómo fijan capacidad máxima y entradas de cortesía?
12. **CONFIRMADO:** solo usuarios con sesión en P1 (alumnos/tutores). ¿Cómo manejan entrega/ingreso, cortesías, cancelaciones y reembolsos?

## 4. Sitio, soporte y datos
13. **INDICADO:** logo y colores del instituto disponibles (materiales por entregar); dominio aún no definido. **PENDIENTE:** nombre comercial exacto, fotos/textos autorizados, dirección, dominio disponible.
14. ¿Qué teléfonos, email y canales usan para reclamos o recuperaciones de cuenta? ¿Qué horas de soporte esperan?
15. ¿Cuál es el presupuesto máximo inicial y de mantenimiento mensual? ¿Quién pagará hosting, dominio y comisiones?
16. **SOLICITADO:** nombre completo, fecha de nacimiento, DNI, teléfono y posibles datos de salud. **PENDIENTE/CRÍTICO:** justificar cada dato; los de salud son sensibles y no se incorporarán por defecto; política de privacidad, seguridad, retención, derechos y menores requieren análisis específico.

## 5. Observación operativa (no solo entrevista)
- Observar con permiso cómo registran una inscripción real y una mensualidad.
- Simular una cuota vencida, un pago por transferencia sin referencia y un comprobante incorrecto.
- Revisar un ejemplo anónimo del cronograma actual y el registro de pagos.
- Confirmar excepciones de negocio antes de escribir modelos.

## Decisiones abiertas bloqueantes
- [ ] Reglas exactas de monto, vencimiento, inscripción y descuentos.
- [ ] Cuentas para menores/tutores y política de privacidad.
- [ ] Flujo de validación de transferencias y emisor legal de comprobantes.
- [ ] Método web de auth (sesión Django con cookies/CSRF y SSR Next) validado con spike técnico.
- [ ] Proveedor y condiciones comerciales de Mercado Pago, comisión/recargo y titularidad de cuenta.
- [x] Ticketing P1 SIN butacas numeradas, solo usuarios autenticados; validar comercialmente antes de comprometer fechas/precio.
- [ ] Presupuesto final, cronograma y soporte posterior.

## Resultado de fase 0
Convertir las respuestas en:
1. Diagrama de flujo actual y flujo futuro de inscripción/pago.
2. Lista P0 cerrada, P1 y no-objetivos.
3. 3 a 5 historias de usuario con criterios de aceptación observables.
4. Riesgos, responsables de decisiones y costo operativo.
5. Confirmación escrita antes de implementación.

## Conciliación: preguntas operativas prioritarias
1. ¿Los pagos por transferencia van a una cuenta bancaria personal de la directora? ¿Se podrán obtener extractos CSV/Excel exportados por el titular?
2. ¿Quién comparará el comprobante del alumno contra un movimiento real, y con qué frecuencia (diaria/semanal)?
3. Si dos alumnos transfieren exactamente el mismo monto sin referencia, ¿qué procedimiento seguirá administración antes de aprobar?
4. ¿Es necesario emitir factura fiscal, recibo interno o solamente historial de pagos? Validar con contador.
5. ¿Los descuentos se aplican por alumno, disciplina, cantidad de disciplinas, hermanos o situaciones excepcionales? Conseguir 2-3 ejemplos anonimizados.
6. ¿Un tutor puede pagar una cuota por cada menor o agrupar varias en una sola operación? No asumir pago combinado P0.

## Preguntas concretas para Ema y dirección (v0.3)
1. ¿Cuántas disciplinas, clases semanales y profesores tienen? ¿Quién da de alta/baja alumnos hoy, en qué planilla y con qué identificadores?
2. ¿Qué significa una disciplina «inactiva»? ¿Se puede reabrir con otro profesor? ¿Puede seguir teniendo cuotas históricas?
3. ¿Cuáles son los roles reales de Miri, Ema y profesores? ¿Quién puede modificar una tarifa, aplicar descuento, corregir una cuota y confirmar pago?
4. Traer **3 ejemplos anónimos de cuotas**: una normal, una con descuento y una con mora. Precisar día de vencimiento y tramos como «1–10»: ¿del mes siguiente?, ¿se acumula?, ¿hay tope o excepciones?
5. Al vencer, ¿qué se restringe exactamente: material privado, inscripción, ticketera o toda la sección académica? ¿Qué sucede con pago informado pero en revisión?
6. ¿Los profesores marcan clase dictada, suspensión o asistencia? ¿Quién aprueba y quién ve los cambios? ¿Cómo funcionan reemplazos y reprogramaciones?
7. Banco y alias/CBU de Miri, acceso a extractos CSV/Excel, quién concilia, tiempos de verificación y cómo resuelven transferencia sin referencia. Solicitar datos exactos **solo en configuración privada, cuando haga falta**.
8. ¿La directora tiene cuenta MP apta para cobrar? ¿Se autoriza recargo por MP, cómo se informa y qué operación recibe comprobante fiscal? Contador confirma recibo interno vs factura.
9. Datos personales: ¿necesitan DNI completo y fecha exacta? ¿Existe necesidad justificada de información médica en un instituto de danza y un proceso seguro alternativo? Consultar asesoría jurídica antes de recogerla.
10. ¿Hay logo, paleta y fotografías con autorización de publicación? ¿Cuál es el dominio/nombre comercial disponible?

## Decisiones que NO debe tomar Codex
- Fórmula/tasa del recargo entre días 1 y 10; excepciones y prorrateos.
- Formato de clases dictadas o asistencias, y cambio de profesor histórico.
- Política exacta de bloqueo por deuda; nunca inventar restricciones por sí mismo.
- Reglas de factura fiscal ni supuestas capacidades de conciliación bancaria automática.
- Recopilación de condiciones médicas, destinatarios/permisos y plazos de retención.
