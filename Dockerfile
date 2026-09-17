ARG PYVER=3.12
FROM ghcr.io/astral-sh/uv:python${PYVER}-trixie-slim

ENV UV_NO_DEV=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies in their own layer, cached independently.
COPY uv.lock pyproject.toml ./
RUN uv sync --locked --no-install-project --no-build --extra all

ARG APP_VERSION=0.0.0

LABEL org.opencontainers.image.title="SimDB" \
      org.opencontainers.image.description="ITER Simulation Management Tool" \
      org.opencontainers.image.source="https://github.com/iterorganization/SimDB" \
      org.opencontainers.image.licenses="LGPL-3.0-only" \
      org.opencontainers.image.version="${APP_VERSION}" \
      io.simdb.component="server"

# Add the project source and finish the sync.
ENV SETUPTOOLS_SCM_PRETEND_VERSION="${APP_VERSION}"
COPY alembic.ini ./
COPY src/ ./src/
COPY alembic/ ./alembic/
RUN uv sync --locked --extra all

ENV SIMDB_SITE_CONFIG_PATH=/app/config/simdb.cfg

EXPOSE 5000

# Run under Gunicorn rather than the Werkzeug dev server
CMD ["uv", "run", "gunicorn", "--bind=0.0.0.0:5000", "--workers=3", "--access-logfile=-", "--error-logfile=-", "simdb.remote.wsgi:app"]

