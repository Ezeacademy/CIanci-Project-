# Registro de decisiones y pendientes — 24/10/2026

**Estado:** Declaraciones del desarrollador para convertir en requisitos. No equivalen a aprobación contractual por Ema/Miri ni autorizan implementar cálculos/acciones ambiguas.

## Confirmado o expresamente pedido por el desarrollador
- Diversas disciplinas. Deben crearse/desactivarse/reactivarse sin perder historia; los profesores pueden cambiar.
- Administración (Ema y directora Miri) necesita cambiar tarifas. Queda por decidir si basta Django Admin; propuesta técnica P0: sí.
- Existe esquema de recargos por mora por días/tramos (menciona 1–10); montos, fechas y escalamiento sin confirmar.
- Usuarios con mensualidades impagas deberán tener funcionalidades restringidas; no bloquear autenticación, pago o reclamos.
- Profesor como rol diferenciado y calendario integrado, con horarios y posibilidad de informar dictado/suspensión de clases.
- Cuenta bancaria receptora prevista a nombre de Miri Cianci; alias y datos exactos faltan. No inventar.
- Instituto dispone de identidad visual y canales de contacto por recopilar; aún no tiene dominio definido.
- Datos de alumnos mencionados: nombre completo, fecha nacimiento, documento, teléfono; quizá información sanitaria (dato sensible de alta protección).
- Mercado Pago con eventual recargo a confirmar; transferencias bancarias con trazabilidad; recibo interno para el alumno verificable server-side.
- Ticketera P1 con usuarios autenticados, cupo general sin butacas numeradas; interfaz tipo ticketera.

## Recomendaciones técnicas aún por aprobar
1. Django Admin para Ema/Miri en P0 y frontend Next.js para alumnos/profesores; permiso limitado por acción y objeto.
2. Estado activo/inactivo y relaciones de asignación docente con vigencias. No soft-delete universal.
3. Precios versionados por vigencia; cuotas emitidas con monto aplicado histórico (snapshot), ajustes auditados.
4. `billing` determina mora/elegibilidad; `payments` no decide precios; `academy` no decide acceso financiero.
5. Acceso limitado por deuda a funciones concretas, nunca bloqueo de login/deuda/pago/soporte; aclarar pagos en revisión.
6. Webhooks firmados de Mercado Pago al backend + verificación server-to-server, idempotencia; frontend refresca estado por API. WebSockets y Django signals no son mecanismos necesarios para verificar cobros.
7. Transferencia externa a cuenta bancaria: validación manual contra movimiento bancario salvo integración bancaria disponible/autorizada. Stripe no confirma transferencias ajenas a su propia red de pagos.
8. Constancia interna tras pago acreditado, con ID aleatorio y verificación de estado/permiso por servidor; QR/PDF puede copiarse. Confirmar recibos fiscales con contador.
9. **Datos de salud fuera de P0** hasta revisión de necesidad, fundamento jurídico y controles de privacidad. Datos personales mínimos, protección adicional para menores.

## Pendientes prioritarios para Ema y Miri
- Cantidad alumnos, profesores, clases y operaciones actuales.
- Regla precisa de precios combinados, descuentos, tramos de mora, períodos/gracia y ajuste de cuotas emitidas.
- Restricción funcional exacta de usuarios morosos, excepciones y apelaciones.
- Calendario: reporte de profesor, estados, reemplazos, cancelaciones, asistencia y responsable final.
- Conciliación bancaria: exportación de movimientos, referentes, tiempos y detección de ambigüedades.
- Proceso fiscal/contable: recibo interno vs factura, tratamiento de recargo de MP.
- Tutores de menores, protección de privacidad, necesidad real de cada dato y autorización de medios audiovisuales.
- Materiales institucionales: paleta, logo, fotos, horarios, medios de contacto, nombre final y dominio.

## Documentación oficial consultada
- Mercado Pago: https://www.mercadopago.com.ar/developers/es/docs/checkout-pro-orders/notifications
- Argentina AAIP: https://www.argentina.gob.ar/aaip/datospersonales/derechos
- Ley 25.326: https://www.argentina.gob.ar/normativa/nacional/64790/actualizacion
