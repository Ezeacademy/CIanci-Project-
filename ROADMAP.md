# Roadmap con puertas de aprobación (sin ciclos de perfeccionamiento)

**Regla central:** trabajo en rebanadas verticales pequeñas; solo una en curso; terminar/verificar/aceptar antes de empezar otra. La base técnica no habilita inmediatamente todos los módulos.

## Fase 0 — Descubrimiento, sin código
- Reunión con dirección: cantidad alumnos, clases y planes; ciclo de facturación; pagos; procesos de validación; eventos; roles; datos y operación actual.
- Entregar flujos reales, 3-5 historias prioritarias, P0/P1 aprobados, decisiones abiertas cerradas o marcadas bloqueantes.
- **Fin:** product owner confirma scope, precio/etapas, tratamiento de datos y forma de cobro. STOP.

## Fase 1 — Base reproducible
- Crear únicamente backend Django/DRF, frontend Next/TS, PostgreSQL y Compose, healthcheck y CI básicos. Lockfiles, formatter, linters, tests smoke, env.example seguro.
- Comprobar que ambos levantan, migraciones ejecutan, base conecta, frontend construye y API responde.
- **Fin:** comandos reproducibles documentados; tests + lint + typecheck/build pasan. STOP.

## Fase 2 — Cuentas y permisos
- User personalizado desde primera migración, roles alumno adulto/tutor/admin, vínculo tutores-menores validado, login/logout/recovery según flujo acordado, pantalla de acceso, `/api/v1/me/`.
- Verificar sesión/cookies/CSRF con SSR de Next y DRF antes de ampliar la aplicación.
- **Fin:** alumno A nunca ve B; admin autorizado; no autenticado obtiene 401/403 según contrato; tests positivos y negativos. STOP.

## Fase 3 — Instituto y calendario
- Disciplinas, horarios, docentes e inscripciones múltiples de alumnos a disciplinas; catálogo público y panel básico de alumno/tutor; administración por Django Admin.
- **Fin:** personal edita clase, web refleja cambios y estudiante ve solo sus clases privadas; pruebas. STOP.

## Fase 4 — Cuotas y transferencias
- Tarifas configurables, cuotas con snapshot de precio, ajustes/descuentos simples auditados y vencimiento fin de mes (pendiente aprobación), historial, detalle de alias/CBU, carga de referencia/comprobante validada, revisión manual/admin, reporte conciliable (fechas, usuario, monto, referencia, estado, revisor), exportación administrativa y auditoría.
- **Fin:** no duplica cuotas, un alumno no altera pago de otro, comprobante no marca pagado, aprobación queda registrada; pruebas. STOP.

## Fase 5 — Mercado Pago en sandbox
- Crear orden en backend con importe definido por cuota, redirección Checkout Pro, webhook firmado, verificación contra API externa, idempotencia y transición de estado.
- Casos: aprobado, pendiente, rechazado, repetido, fuera de orden, payload adulterado e indisponibilidad de proveedor.
- **Fin:** ninguna notificación válida repetida produce doble aplicación de pago; suite pasa con mocks y una verificación real sandbox separada. STOP.

## Fase 6 — Despliegue controlado
- Infra, dominio, secretos, backups/restauración probada, settings prod, monitoreo básico y checklist Django; prueba de aceptación con administración.
- **Fin:** despliegue autorizado, flujo alumno→pago→confirmación demostrado, rollback definido. STOP.

## Fase 7 — Ticketing simple (posterior a MVP P0)
- Event/Function/Ticket, cupo general, compra por usuarios autenticados, checkout y QR con token no adivinable para validación; evitar dobles entradas. UI de ticketera con contador de entradas restantes; no hay butacas, WebSockets ni reservas temporales.
- **Fin:** compra y validación única con tests, con cancelaciones y reembolsos definidos. STOP.

## Backlog P2 (requiere nuevo alcance)
Butacas numeradas y reservas concurrentes, actualización en vivo, app React Native, multi-instituto, débitos automáticos, integraciones contables, reportes avanzados.

## Definition of Done por historia
- [ ] Requisito y criterios de aceptación especificados, sin alcance ambiguo.
- [ ] No se cambió código ajeno ni se añadieron abstracciones/paquetes innecesarios.
- [ ] Seguridad y permisos probados si aplican; casos límite y errores cubiertos.
- [ ] Migrations/constraints y transacciones revisadas cuando hay datos.
- [ ] Test unitario/integración apropiado ejecutado, con resultado observable.
- [ ] Lint, typecheck y build relevantes ejecutados; sin warnings graves nuevos.
- [ ] Contrato API/README actualizados solo si cambiaron.
- [ ] Diff y decisiones relevantes resumidos; riesgos y pendientes visibles.
- [ ] Demo manual del flujo verificable (cuando aplique).
- [ ] **Aprobación explícita** antes de avanzar de historia o fase.

## Política ante mejoras y bugs
- Mejoras «podría optimizarse» van a backlog, no a la fase actual, salvo bug, problema de seguridad o bloqueo del criterio de aceptación.
- Refactor permitido solo por deuda evidente que impide la historia; mínimo cambio y tests verdes.
- No repetir ensayos sin nuevo diagnóstico. Tras dos intentos fallidos razonables: STOP, evidencias y opciones para el usuario.
- Tests realmente ejecutados; nunca declarar un despliegue, prueba, integración o commit inexistente.

## Prompt de fase recomendado
> Leé `AGENTS.md`, `PRODUCT_SCOPE.md`, `ARCHITECTURE.md` y `ROADMAP.md`. Estamos autorizando solo **Fase X / Historia Y**. Primero informá: objetivo concreto, archivos que tocarías, riesgos, tests y criterios de aceptación. **No implementes hasta mi aprobación.** No agregues features futuras ni nuevas dependencias sin justificar. Al implementar, ejecutá verificaciones, informá resultados reales y detenete. No avances a otra historia/fase, ni hagas commit, push o deploy sin pedir permiso.

## Política de agentes para cada fase
- Un único coordinador responsable de aprobar plan, distribuir tareas, integrar y verificar; el agente principal mantiene contexto breve.
- Delegar si la tarea es delimitable y aporta beneficio neto (exploración selectiva, implementación de módulo aislado, revisión). Tareas triviales se realizan directamente.
- Máximo dos subagentes concurrentes, como regla conservadora; por defecto un único agente escritor por fase/historia. Nunca editar el mismo archivo en paralelo.
- Primero explorar contratos/rutas afectadas; luego implementar; después revisar. Se pueden solapar exploración y lectura, no fases de implementación dependientes.
- Subagentes reportan evidencia resumida: archivos, cambios, pruebas ejecutadas y resultado, riesgos, bloqueos. El coordinador verifica lo necesario; no acepta únicamente «éxito».
- Parar tras la aceptación de criterios; no lanzar revisiones ni refactors recursivos. Historial durable en documentos y git, no en enormes conversaciones transferidas.

## Notas de alcance añadidas v0.3
- Fase 2: definir también profesor y personal administrativo (Miri/Ema), permisos mínimos y acceso a perfiles de menores.
- Fase 3: probar disciplina inactiva/reactivada, reemplazo de docente con histórico, calendario de eventos y reporte de dictado/cancelación (solo tras acuerdo sobre estados).
- Fase 4: Ema debe aprobar fórmula de mora y regla exacta de acceso limitado antes de implementarlas. Recepción de transferencias usa verificación manual real. Constancia interna verificable posterior a pago, no «QR imposible de copiar».
- Fase 5: preferir simple webhook validado + consulta API + actualización de frontend por nueva consulta; prohibido agregar WebSockets/señales sin necesidad probada.
- Antes de recolectar información sobre condiciones médicas: STOP, evaluar necesidad y normativa de datos sensibles. Excluido de la implementación base.
