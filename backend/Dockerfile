FROM python:3.12-slim

WORKDIR /app

# curl: the HEALTHCHECK below probes /health
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 appuser

# Dependency layer: manifest + package source, non-editable install.
# .dockerignore keeps .env / .venv / tests out of the build context.
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser reroute ./reroute
RUN pip install --no-cache-dir .

# Runtime files not packaged by setuptools: alembic migrations + entrypoint.
# Startup runs `alembic upgrade head` via the installed alembic (portable).
COPY --chown=appuser:appuser alembic.ini run.py ./
COPY --chown=appuser:appuser alembic ./alembic

USER appuser

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# start-period covers DB/Redis connect + migration on first boot
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["python", "run.py"]
