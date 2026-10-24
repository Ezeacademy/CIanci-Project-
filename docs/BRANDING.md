# Cianci Platform — Branding y contenido institucional (borrador v0.1)

**Fuente:** captura de perfil de Instagram aportada por el cliente el 24/10/2026.  
**Estado:** referencia inicial, pendiente de validación con Miri y Ema.  
**Uso:** orientar la propuesta UI-01. No sustituye los archivos oficiales de marca ni autoriza publicar información no confirmada.

## 1. Datos observados en la captura

| Campo | Valor observado | Estado |
| --- | --- | --- |
| Nombre público | **Instituto de Danzas Cianci** | Observado en perfil; validar denominación legal/comercial |
| Instagram | **@institutocianci** | Observado |
| Lema | **Formando profesores y bailarines desde 1985** | Observado; confirmar uso del texto en sitio |
| Barrio / ciudad | **Villa España, Berazategui, Buenos Aires, Argentina** | Observado parcialmente; validar provincia y ubicación para mapa |
| Dirección mostrada | **Calle 150, número 2501** | Observado; confirmar formato oficial y exactitud |
| Enlace de contacto mostrado | **wa.me/1558073069** | Capturado literalmente; NO publicar ni convertir a enlace hasta validar teléfono completo con código de país |
| Dominio oficial | Pendiente | No inventar |
| Correo electrónico | Pendiente | No inventar |
| Teléfono institucional | Pendiente | No inferir del enlace abreviado |

Los contadores de seguidores/seguidos son datos transitorios de Instagram: no deben incorporarse a la web como contenido fijo.

## 2. Identidad visual observada

- Emblema/escudo de contorno claro con **dos figuras de danza** en su centro.
- Fondo del emblema **bordó / rojo vino oscuro**.
- Trazos blancos o marfil y anillos decorativos claros alrededor del escudo.
- El **aro exterior multicolor rosado/amarillo** que aparece en la captura corresponde a la interfaz de Instagram (historias), **NO** debe copiarse como parte del logotipo.
- El fondo casi negro de la captura es la interfaz de Instagram en modo oscuro, **NO** un color oficial del instituto.

### Colores provisionales muestreados de la captura

| Token provisorio | HEX aproximado | Uso sugerido | Validación |
| --- | --- | --- | --- |
| `brand-primary` | `#770306` | Acentos, CTA, títulos destacados | **Pendiente:** obtener archivo de marca original |
| `brand-primary-dark` | `#580000` | Estados oscuros/hover, sujeto a contraste | Propuesta derivada, NO color oficial confirmado |
| `brand-on-primary` | `#FFFFFF` | Texto sobre fondo bordó, comprobar contraste | Provisional |
| `surface` | `#FAF8F5` | Fondo claro cálido de la web | **Propuesta de diseño**, NO extraída del logo |
| `text-primary` | `#211B1B` | Texto de lectura | **Propuesta de diseño**, NO extraída del logo |

**Nota:** los valores son orientativos: una captura comprimida no permite recuperar la paleta exacta. No asignar carácter de «color oficial» a estos HEX. Al recibir el logo original, muestrear de nuevo y aprobar tokens definitivos.

## 3. Dirección UI-01

- Identidad elegante, artística y legible, respetando el bordó del escudo.
- Priorizar fotografía real autorizada de las clases y presentaciones, sin inventar profesores, horarios ni testimonios.
- Homepage: encabezado con identidad, presentación, disciplinas, instituto, profesores (solo con datos validados), horarios (indicar expresamente si son ejemplos), contacto y pie de página.
- Componentes de Next.js accesibles y responsive; sin nuevas dependencias de animación por defecto.
- Tokens CSS/Tailwind centralizados; evitar colores hardcodeados repetidos.
- Los CTA deben navegar a contenido real; no simular pagos ni inscripciones todavía.
- Si no se dispone del logo original, usar **marca tipográfica temporal** con el nombre institucional en lugar de estirar la miniatura de 150 × 150 píxeles o redibujar el escudo.

## 4. Materiales pendientes para completar la marca

1. Logo original en SVG (ideal), PNG transparente de buena resolución, o archivo editable autorizado.
2. Colores y tipografías oficiales, si existen, y variantes de marca para fondo claro/oscuro.
3. Fotografías autorizadas de clases, docentes, salones y funciones; permisos de uso y consentimiento si hay menores identificables.
4. Confirmación de nombre, lema «desde 1985», dirección, WhatsApp completo, correo e Instagram oficial.
5. Lista actual de disciplinas, docentes y horarios confirmados por administración.
6. Referencias de diseño aprobadas y contenido institucional definitivo.

## 5. Límites del trabajo para Codex

- Este archivo sirve como **fuente de referencia**, no como permiso automático de implementación.
- No descargar ni enlazar en producción la URL firmada de CDN de Instagram: puede caducar y su miniatura tiene baja resolución.
- No usar material visual de terceros sin autorización ni publicar datos de menores sin permiso.
- No inventar valores de cuotas, profesores, horarios ni información de contacto.
- Proponer UI-01, indicar lo provisional y solicitar aprobación antes de editar código (según `AGENTS.md`).
