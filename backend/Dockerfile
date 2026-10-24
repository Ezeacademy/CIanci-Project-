FROM python:3.13.17-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.5
COPY pyproject.toml uv.lock ./
RUN uv sync --locked
COPY . .
EXPOSE 8000
CMD ["uv", "run", "--locked", "python", "manage.py", "runserver", "0.0.0.0:8000"]
