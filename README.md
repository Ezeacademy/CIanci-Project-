# Cianci Platform

Base local reproducible — F1-01. Django/DRF, Next.js y PostgreSQL en servicios independientes. Esta entrega no implementa funcionalidades de negocio ni está preparada para despliegue productivo.

## Requisitos y versiones

Docker Engine con el plugin Docker Compose y acceso al daemon. No hace falta instalar Python, Node o PostgreSQL en el host.

| Componente | Versión fijada |
| --- | --- |
| Python | 3.13.17 |
| Django / DRF | 5.2.18 LTS / 3.16.1 |
| PostgreSQL / Psycopg | 17.11 / 3.3.6 |
| Node.js | 24.22.1 LTS |
| Next.js / React | 16.4.3 / 19.3.1 |
| TypeScript / Tailwind | 5.9.3 / 4.3.3 |
| uv / Ruff | 0.13.5 / 0.17.2 |
| ESLint / Prettier | 9.39.5 / 3.9.10 |

`backend/uv.lock` y `frontend/package-lock.json` fijan dependencias transitivas. Los builds usan `uv sync --locked` y `npm ci`. Django 5.2 mantiene una base LTS y DRF 3.16 soporta Django 5.2/Python 3.13. Psycopg conecta PostgreSQL; su distribución binaria evita herramientas de compilación locales. uv administra el lockfile Python y Ruff cubre lint/formato con una herramienta. ESLint, Prettier y Tailwind responden a la arquitectura acordada. Los tests usan los runners nativos de Django y Node, sin servicios adicionales.

ESLint 9.39.5 es la última versión compatible con los peers de `eslint-config-next` elegidos. npm avisa que esa rama ya no tiene soporte; ESLint 10 todavía entra en conflicto con plugins transitivos de esta configuración. Se conserva compatibilidad sin forzar peers; su actualización queda pendiente cuando el ecosistema Next la permita.

## Primera ejecución

Desde la raíz:

```bash
cp .env.example .env
```

Editar `.env` y completar `POSTGRES_PASSWORD` y `DJANGO_SECRET_KEY` con valores aleatorios privados distintos. Se pueden generar dos valores con `openssl rand -hex 32`. No pegar secretos en comandos compartidos ni subir `.env` al repositorio. Compose rechaza valores vacíos; `.env.example` no contiene credenciales operativas.

```bash
docker compose config --quiet
docker compose build
docker compose up -d --wait db
docker compose run --rm backend uv run --locked python manage.py migrate --noinput
docker compose up -d --wait
docker compose ps
```

- Frontend: <http://localhost:3000>.
- API: <http://localhost:8000/api/v1/health/>.
- PostgreSQL: solo red interna, host `db`, puerto `5432`.

Los puertos HTTP se publican exclusivamente en `127.0.0.1`. El backend recibe credenciales por variables de entorno; el frontend no recibe credenciales. PostgreSQL conserva datos en el volumen `postgres_data`. La cuenta local creada por la imagen PostgreSQL permite crear la base temporal de tests; no es una configuración de permisos de producción.

`backend/config/settings/` separa base, desarrollo y tests. Auth, admin, contenttypes y sesiones no están instalados. DRF usa `UNAUTHENTICATED_USER=None` y ningún autenticador; únicamente el healthcheck permite acceso público. No se crean tablas `auth_user` ni sesiones. `migrate` ejecuta el mecanismo de migraciones y, en esta fase sin modelos, informa que no hay migraciones para aplicar. En Fase 2 debe definirse el usuario personalizado antes de habilitar esas aplicaciones y ejecutar sus migraciones.

## Desarrollo cotidiano

```bash
docker compose up -d --wait
docker compose logs -f backend frontend
docker compose restart backend frontend
docker compose down
```

El código se monta desde el host y ambos servidores recargan cambios. Las dependencias Python quedan en `/opt/venv`, fuera del montaje. `node_modules` y `.next` usan volúmenes propios. `docker compose down` conserva los volúmenes; no usar `down -v` si se quieren conservar datos.

Tras un cambio aprobado de dependencias, actualizar el lockfile correspondiente y reconstruir. Para sincronizar el volumen npm existente con su lockfile:

```bash
docker compose build
docker compose run --rm frontend npm ci
docker compose up -d --wait
```

Cambiar `POSTGRES_PASSWORD` en `.env` no cambia la contraseña de una base ya inicializada. Conservar las credenciales locales asociadas al volumen; cualquier reinicialización que elimine datos requiere una decisión explícita.

## Contrato del healthcheck

`GET /api/v1/health/` ejecuta `SELECT 1` contra PostgreSQL y devuelve JSON con `Cache-Control: no-store`.

| Situación | HTTP | Cuerpo |
| --- | --- | --- |
| Base accesible | 200 | `{"status":"ok"}` |
| Error de base | 503 | `{"status":"unavailable"}` |
| POST, PUT, PATCH o DELETE | 405 | Error estándar DRF de método no permitido |

El endpoint no necesita credenciales ni devuelve excepciones, direcciones de base, versiones o secretos. Es una comprobación de disponibilidad de API y base, no una prueba exhaustiva del sistema. OpenAPI se incorporará junto con endpoints de negocio reales.

```bash
curl --fail http://localhost:8000/api/v1/health/
curl --fail http://localhost:3000/
```

## Verificaciones

Con los servicios saludables:

```bash
docker compose exec backend uv run --locked python manage.py check
docker compose exec backend uv run --locked python manage.py makemigrations --check --dry-run
docker compose exec backend uv run --locked python manage.py test --settings=config.settings.test
docker compose exec backend uv run --locked ruff check .
docker compose exec backend uv run --locked ruff format --check .
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check
docker compose exec frontend npm run typecheck
docker compose exec frontend npm test
```

Los cuatro tests backend comprueban PostgreSQL real y GET público, fallo de base sin detalles internos, métodos de escritura rechazados y ausencia de aplicaciones/migraciones/tablas de autenticación. La prueba de humo Node realiza una petición HTTP al frontend levantado y verifica contenido e idioma. `typecheck` genera los tipos de Next y ejecuta TypeScript estricto.

El build se ejecuta en un contenedor separado, sin montajes de desarrollo, para evitar interferencias con `.next` o el servidor activo:

```bash
docker build --tag cianci-frontend-check frontend
docker run --rm cianci-frontend-check npm run build
```

Para aplicar formato intencionalmente:

```bash
docker compose exec backend uv run --locked ruff format .
docker compose exec frontend npm run format
```

`.github/workflows/ci.yml` genera credenciales efímeras, construye y levanta los tres servicios, espera healthchecks, ejecuta migraciones, tests, lint, formato, typecheck, smoke y build aislado. Siempre detiene los servicios al finalizar. La ejecución remota de CI requiere que el repositorio esté alojado en GitHub y el workflow habilitado; no se configura ningún remoto ni despliegue en esta fase.

## Alcance y documentos

- `AGENTS.md`: límites de ingeniería, aprobación y coordinación.
- `ARCHITECTURE.md`: responsabilidades y arquitectura del monolito modular.
- `PRODUCT_SCOPE.md`, `DISCOVERY.md`, `DECISIONS_2026-10-24.md`: requisitos y decisiones de negocio pendientes.
- `ROADMAP.md`: fases y condiciones de salida.

Esta base no cierra los pendientes de descubrimiento ni autoriza autenticación, alumnos, cobros, calendarios, ticketera o despliegue. No incluye datos reales. La configuración productiva y la definición del usuario personalizado pertenecen a fases posteriores, con aprobación independiente.
