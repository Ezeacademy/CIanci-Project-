# Instrucciones permanentes para Codex — Cianci Platform

## Propósito y fuentes de verdad
Aplicación para un instituto de danza: web pública, autenticación de alumnos, clases, calendario, mensualidades y pagos. El alcance vigente está en `PRODUCT_SCOPE.md`; la arquitectura aprobada, en `ARCHITECTURE.md`; la secuencia y condiciones de salida, en `ROADMAP.md`. Si un requisito no está especificado, marcarlo como **PENDIENTE** y preguntar; no inventarlo.

## Reglas inviolables
1. Trabajar **una fase y una historia aprobadas por vez**. Antes de cambiar código, informar: objetivo, archivos impactados, criterios de aceptación, riesgos y plan mínimo de tests. No empezar la fase siguiente sin autorización explícita.
2. Priorizar corrección, seguridad, claridad y mantenibilidad sobre elegancia abstracta. Aplicar KISS, YAGNI, DRY, separación de responsabilidades y SOLID con pragmatismo.
3. Mantener **Django + DRF como única autoridad del dominio y los pagos**; Next.js solo representa la UI y actúa como cliente de la API. No duplicar reglas de negocio ni fuentes de verdad.
4. Backend = **monolito modular**, no microservicios. Respetar propietarios y contratos de módulos descritos en `ARCHITECTURE.md`. Evitar imports circulares, lógica de pago en vistas, serializers gigantes y módulos `utils` indiscriminados.
5. Antes de crear cualquier helper, hook, componente, servicio, modelo o dependencia, buscar equivalentes existentes. Reutilizar cuando representen realmente el mismo concepto; no crear abstracciones solo para eliminar una línea repetida.
6. No introducir Redis, Celery, WebSockets, colas, Kubernetes, repositorios abstractos, buses de eventos, GraphQL ni multi-tenancy sin requisito aprobado, explicación del problema y evidencia de necesidad.
7. Frontend: TypeScript estricto; respetar límites Server/Client de Next; keys estables; evitar estado duplicado y efectos innecesarios. No agregar `memo`, `useMemo`, `useCallback` o caché por rutina: justificar con una medida o un problema claro.
8. API: validar entrada, comprobar permisos por **objeto y acción**, devolver errores consistentes; mantener contratos versionados. No exponer secretos al browser.
9. Pagos: nunca confiar en precios enviados por el cliente, comprobantes de transferencia, redirecciones de checkout ni payloads de webhooks sin validar. Mantener idempotencia de confirmación, trazabilidad, y pruebas de duplicados/fallos. No procesar dinero real sin aprobación explícita.
10. PostgreSQL: aplicar restricciones de unicidad/integridad y transacciones breves cuando corresponda. Guardar importes sin `float`; definir una representación monetaria consistente. Prohibidas migraciones destructivas sin aprobación y plan de recuperación.
11. Tests de flujos felices, permisos, fallos y casos límite de la historia. Ejecutar realmente los checks relevantes; no afirmar que pasaron si no se ejecutaron. Si no pueden correrse, informarlo.
12. No tocar funcionalidades ajenas al alcance, no realizar refactorizaciones globales «de limpieza», no actualizar versiones ni añadir dependencias sin motivo documentado. No cambiar infraestructura, secretos, configuración remota, Git remoto ni despliegues sin autorización explícita.
13. Si los criterios ya se cumplen, **detenerse**. No seguir «mejorando» por iniciativa propia. Si un error sigue sin resolverse tras dos enfoques razonables, detener cambios exploratorios y presentar diagnóstico/opciones.

## Formato de entrega obligatorio
- Cambios realizados y por qué.
- Archivos modificados.
- Evidencia de aceptación: comandos y resultados de tests/lint/typecheck/build pertinentes.
- Riesgos, decisiones y pendientes.
- Confirmación de que no se trabajó fuera de la fase.
- **STOP**: solicitar aprobación antes de otra fase, refactor o despliegue.

## Orquestación de subagentes de Codex (política v0.3)
- El agente principal es **coordinador/integrador**: interpreta historia, comprueba límites, pide aprobación antes de implementar, delega tareas atómicas, revisa evidencia, verifica aceptación y se detiene. No distribuye objetivos ambiguos como «mejorá el proyecto».
- Usar subagentes solo cuando aporten velocidad, aislamiento de contexto o revisión independiente; nunca delegar tareas triviales por obligación. Límite operativo inicial: **máximo 2 subagentes simultáneos** y **solo 1 agente escritor** durante una historia.
- Roles disponibles: `cianci_explorer` (solo lectura), `cianci_worker` (único escritor, cambios autorizados en archivos especificados), `cianci_reviewer` (solo lectura; calidad, seguridad, tests). Priorizar exploración/revisión ligera antes que paralelismo de escrituras.
- No permitir que subagentes creen nuevos subagentes sin permiso expreso del coordinador. No encadenar revisores/refactors de manera recursiva.
- Entregar a cada subagente: historia y criterios de aceptación, paths autorizados, archivos o contratos mínimos, límites, tests y formato de reporte. No reenviar todo el historial de conversación.
- Cada subagente debe devolver como máximo un resumen útil: estado (éxito/bloqueado), archivos tocados, 3-6 hallazgos significativos, pruebas ejecutadas con resultado y riesgos. No verter logs completos en el hilo principal salvo error relevante.
- El coordinador NO marca la tarea como exitosa solo por una notificación. Revisa el diff/contrato, comprueba pruebas y criterios de aceptación, integra y se detiene. Si el subagente declara que no pudo verificar algo, se informa explícitamente.
- No usar subagentes como herramienta de reducción automática de costos: cada agente hace sus propias llamadas. Medir tiempo/tokens y simplificar si no hay beneficio real. Elegir modelos ligeros para tareas mecánicas solo si están habilitados en la cuenta.
- Configuración sugerida bajo `.codex/config.toml` y agentes en `.codex/agents/`; son límites de coordinación, NO garantizan sandbox de solo lectura por sí solos. Mantener permisos reales de la sesión en modo restringido.

## Guardas específicas de negocio v0.3
- Consultar `DECISIONS_2026-10-24.md` al planificar módulos de administración, calendario, mora, permisos y constancias; `DISCOVERY.md` contiene cuestiones pendientes. Los documentos no autorizan implementar reglas de mora no acordadas.
- No bloquear login ni medios para regularizar pagos; aplicar restricciones solo cuando negocio apruebe acciones/condiciones exactas.
- No recopilar información médica de alumnos ni añadir campos para diagnósticos sin revisión y autorización explícitas. No poner datos de menores, DNI o información sensible en logs o comprobantes públicos.
- No convertir una constancia interna en una supuesta factura fiscal. Una imagen/QR puede copiarse: validación se realiza contra el servidor y permisos.
- No afirmar que Stripe/MP pueda verificar una transferencia externa a cuenta personal sin integración bancaria autorizada.

## Testing proporcional al riesgo
- Para cambios visuales, CSS, layouts y contenido estático, priorizar verificaciones básicas y revisión visual.
- Ejecutar lint, typecheck y una comprobación de compilación al finalizar la historia; no repetir toda la batería después de cada modificación menor.
- Si falla una verificación, corregir la causa y repetir solo las comprobaciones afectadas. Ejecutar la validación final necesaria cuando el resultado esté estable.
- No crear tests que solo verifiquen textos, colores, clases CSS o detalles de implementación sin valor funcional.
- Mantener pruebas existentes cuando protejan comportamientos importantes; actualizar smoke tests únicamente cuando corresponda.
- No agregar Playwright, Vitest ni dependencias de testing sin necesidad justificada.
- Reservar pruebas profundas para autenticación, permisos, pagos, mensualidades, integridad de datos, webhooks, entradas y concurrencia.
- No delegar revisiones independientes de modificaciones visuales triviales; usar subagentes solo cuando el beneficio justifique su costo.
- No ejecutar verificaciones duplicadas que no aporten evidencia adicional.
- No declarar exitosas comprobaciones no ejecutadas; informar siempre las limitaciones.
