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
12. Modificar únicamente los archivos necesarios para la historia aprobada. No tocar funcionalidades ajenas, reformatear o refactorizar por limpieza, ni actualizar versiones o añadir dependencias sin motivo documentado. Actualizar documentación solo si el cambio la vuelve incorrecta. No cambiar infraestructura, secretos, configuración remota, Git remoto ni despliegues sin autorización explícita.
13. Si los criterios ya se cumplen, **detenerse**. No seguir «mejorando» por iniciativa propia. Si un error sigue sin resolverse tras dos enfoques razonables, detener cambios exploratorios y presentar diagnóstico/opciones.

## Convenciones de código legible
- Usar nombres descriptivos y consistentes: colecciones en plural, entidades individuales en singular y booleanos que expresen una condición (`is_`, `has_`, `can_`). Evitar abreviaturas ambiguas cuando exista un nombre más claro.
- Escribir iteraciones y acceso a relaciones de modo que se identifiquen la colección, la entidad y los valores modificados. Mantener cada función enfocada y separar validación, consultas, cálculos y efectos cuando mejore la comprensión; no crear abstracciones ceremoniales.
- Agregar docstrings en inglés a servicios de dominio, operaciones económicas, funciones con efectos secundarios y lógica no evidente. Explicar reglas, efectos y excepciones relevantes; no repetir el nombre de la función.
- Añadir type hints a servicios y funciones de dominio cuando aclaren entradas y resultados. Los comentarios deben explicar el motivo de decisiones, no traducir el código.

## Formato de entrega obligatorio
- Cambios realizados y por qué.
- Archivos modificados.
- Evidencia de aceptación: comandos y resultados de tests/lint/typecheck/build pertinentes.
- Riesgos, decisiones y pendientes.
- Confirmación de que no se trabajó fuera de la fase.
- **STOP**: solicitar aprobación antes de otra fase, refactor o despliegue.

## Control del historial de Git
- El usuario controla el historial. No ejecutar `git add`, `git commit`, `git push`, `git merge`, `git rebase`, `git reset` ni `git stash` sin autorización explícita para esa operación; no crear commits automáticamente al terminar una tarea.
- No modificar ni descartar cambios existentes sin consultar al usuario. Se permiten comandos de consulta como `git status`, `git diff` y `git log`.
- Al terminar una implementación, dejar los cambios sin staging para revisión. Informar los archivos modificados, el motivo y las pruebas ejecutadas.
- Proponer un mensaje de commit con Conventional Commits, pero no preparar ni registrar el commit hasta que el usuario haya revisado los cambios y autorizado expresamente esa operación.

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
- Para UI, priorizar la comprobación funcional en navegador usando el servidor de desarrollo disponible. No ejecutar builds de producción por defecto; explicar brevemente antes por qué una verificación costosa resulta necesaria.
- Reutilizar contenedores de desarrollo activos con `docker compose exec`; crear contenedores, reconstruir imágenes o preparar entornos aislados solo ante una necesidad técnica concreta.
- Ejecutar primero las pruebas relacionadas con el cambio. Correr suites completas ante impacto transversal, riesgo de regresión o cierre de una etapa; no repetir verificaciones que no aporten evidencia nueva.
- Priorizar integración con PostgreSQL para integridad, pruebas de API para autenticación y permisos, y pruebas funcionales de flujos principales. Usar pruebas unitarias cuando exista lógica aislada que lo justifique; no equiparar cantidad de tests con calidad ni verificar lo mismo en varias capas sin motivo.
- Ejecutar lint y typecheck cuando correspondan al alcance; compilar para producción solo si el riesgo o la etapa lo justifican. Tras corregir una verificación, repetir únicamente las afectadas.
- Si falla una verificación, corregir la causa y repetir solo las comprobaciones afectadas. Ejecutar la validación final necesaria cuando el resultado esté estable.
- No crear tests que solo verifiquen textos, colores, clases CSS o detalles de implementación sin valor funcional.
- Mantener pruebas existentes cuando protejan comportamientos importantes; actualizar smoke tests únicamente cuando corresponda.
- No agregar Playwright, Vitest ni dependencias de testing sin necesidad justificada.
- Reservar pruebas profundas para autenticación, permisos, pagos, mensualidades, integridad de datos, webhooks, entradas y concurrencia.
- No delegar revisiones independientes de modificaciones visuales triviales; usar subagentes solo cuando el beneficio justifique su costo.
- No ejecutar verificaciones duplicadas que no aporten evidencia adicional.
- No declarar exitosas comprobaciones no ejecutadas; informar siempre las limitaciones.

## Logs y elementos técnicos
- Revisar logs, mensajes de depuración y endpoints antes de modificarlos o retirarlos; confirmar su función y consumidores. No eliminar endpoints sin esa comprobación.
- Evitar logs redundantes y detalles técnicos innecesarios en interfaces. Conservar registros útiles para diagnóstico, auditoría y seguridad, sin registrar secretos ni datos personales innecesarios.
- No hacer limpiezas generales: proponer cambios acotados para oportunidades que no sean necesarias para la historia vigente.
Quiero mejorar tu forma de trabajar en Cianci para evitar consumo innecesario de tokens, verificaciones redundantes y modificaciones fuera de alcance.

Revisá `AGENTS.md` y la configuración actual de subagentes.

Proponé una actualización mínima de las instrucciones existentes, sin duplicar reglas.

**Principios obligatorios:**

1. **Alcance estricto:** modificar únicamente los archivos necesarios para cumplir la historia aprobada. No aprovechar una tarea para corregir textos, reorganizar documentación, reformatear archivos o refactorizar código no relacionado.

2. **Testing proporcional:** ejecutar pruebas según el riesgo del cambio. Priorizar tests específicos. No repetir suites completas, builds, linters o verificaciones que no aporten evidencia nueva.

3. **Sin perfeccionismo innecesario:** cuando los criterios de aceptación estén cumplidos, detenerse. No realizar mejoras cosméticas adicionales ni perseguir cambios marginales.

4. **Documentación mínima:** actualizar únicamente documentación que haya quedado incorrecta por el cambio. No reescribir README por preferencias de estilo.

5. **Uso estratégico de subagentes:**
   - Explorer: únicamente cuando una investigación delimitada ahorre trabajo real.
   - Worker: para implementación delegable con límites claros.
   - Reviewer: para cambios de alto riesgo, como autenticación, permisos, pagos o concurrencia.
   - No crear subagentes por obligación.
   - Evitar exploraciones duplicadas y revisiones redundantes.

6. **Transparencia:** al finalizar, informar brevemente qué subagentes utilizaste, para qué y por qué. Si no utilizaste ninguno, indicarlo sin justificar extensamente.

7. **Economía de contexto:** leer solo los archivos relevantes, evitar repetir investigaciones ya realizadas y producir informes concisos.

8. **Autonomía controlada:** no pedir aprobación para cada comando rutinario, pero sí antes de operaciones destructivas, cambios importantes de arquitectura o ampliaciones de alcance.

Antes de modificar `AGENTS.md`, mostrame qué reglas existentes cambiarías o complementarías y por qué.

No modifiques código de la aplicación ni otros documentos.

Esperá mi aprobación antes de aplicar el ajuste.

## Concurrencia, atomicidad y confiabilidad

Diseñá las funcionalidades con criterios de ingeniería de producción, considerando concurrencia, consistencia, atomicidad, idempotencia y posibles fallos distribuidos cuando sean relevantes para la operación.

### Principios

1. **Concurrencia:** identificá posibles condiciones de carrera en operaciones que consultan y modifican estado compartido. No asumas que las solicitudes se ejecutan secuencialmente.

2. **Atomicidad:** cuando varios cambios en la base de datos deban completarse juntos, utilizá transacciones mediante `transaction.atomic()` y definí claramente sus límites.

3. **Integridad:** priorizá restricciones de base de datos (`UNIQUE`, `CHECK`, claves foráneas) para proteger invariantes que deban cumplirse incluso ante solicitudes concurrentes. No dependas exclusivamente de validaciones de aplicación.

4. **Bloqueos:** utilizá mecanismos como `select_for_update()` cuando sean necesarios para coordinar modificaciones concurrentes. Evitá bloqueos innecesarios, transacciones excesivamente largas y consultas externas dentro de transacciones.

5. **Idempotencia:** analizá si una operación puede repetirse por reintentos del cliente, fallos de red, webhooks o procesamiento asíncrono. Implementá garantías de idempotencia cuando el riesgo y las reglas de negocio lo justifiquen.

6. **Fallos distribuidos:** cuando intervengan servicios externos, considerá timeouts, respuestas perdidas, reintentos, duplicaciones y estados parcialmente completados. No supongas que una transacción de base de datos garantiza atomicidad entre sistemas independientes.

7. **Consistencia:** identificá las invariantes del negocio y elegí mecanismos proporcionales para preservarlas. No introduzcas consistencia eventual cuando una transacción local resuelva el problema.

8. **Testing:** probá escenarios de concurrencia, rollback, duplicación o reintentos cuando sean riesgos reales. Priorizá pruebas focalizadas y representativas, no suites extensas por defecto.

### Criterio de diseño

Antes de implementar una operación crítica, preguntate:

- ¿Qué ocurre si dos solicitudes se ejecutan simultáneamente?
- ¿Qué ocurre si falla una operación a mitad del proceso?
- ¿Qué ocurre si el cliente reintenta la solicitud?
- ¿Qué invariantes debe garantizar la base de datos?
- ¿Qué ocurre si un servicio externo responde tarde, falla o duplica un evento?

Aplicá las respuestas solo cuando sean relevantes para la funcionalidad.

**No agregues microservicios, colas, Redis, patrones distribuidos, locks o capas de abstracción sin una necesidad concreta.**

El objetivo es construir un monolito modular simple, correcto y preparado para evolucionar, no anticipar complejidad innecesaria.
