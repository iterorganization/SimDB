# Build stage: Install dependencies and prepare the application
FROM ghcr.io/astral-sh/uv:0.12.17-python3.12-trixie-slim@sha256:9a59bb7206905ccaae4f7dab222fbac47c125a21e5fc16f43f427cd6c940ade3 \
    AS build

ENV UV_LINK_MODE=copy \
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
RUN uv sync --locked --no-dev --no-install-project --no-build --extra all

ARG APP_VERSION=0.0.0

# Add the project source and finish the sync.
ENV SETUPTOOLS_SCM_PRETEND_VERSION_FOR_IMAS_SIMDB="${APP_VERSION}"
COPY alembic.ini ./
COPY docker/gunicorn.conf.py ./docker/gunicorn.conf.py
COPY src/ ./src/
RUN uv sync --locked --no-dev --extra all

ENV SIMDB_SITE_CONFIG_PATH=/app/config/simdb.cfg

# Runtime stage: Minimal image with only runtime dependencies
FROM ghcr.io/astral-sh/uv:0.12.17-python3.12-trixie-slim@sha256:9a59bb7206905ccaae4f7dab222fbac47c125a21e5fc16f43f427cd6c940ade3 \
    AS service

ARG APP_UID=1000
ARG APP_GID=1000

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only runtime dependencies (no build-essential, no *-dev variants, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libldap2 \
    libsasl2-2 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid ${APP_GID} simdb \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin simdb \
    && mkdir -p /data/simdb/simulations /home/simdb/.gunicorn \
    && chown -R simdb:simdb /data/simdb /home/simdb /app

# Copy the prepared application and dependencies from build stage
COPY --from=build --chown=simdb:simdb /app/.venv /app/.venv
COPY --from=build --chown=simdb:simdb /app/alembic.ini ./
COPY --from=build --chown=simdb:simdb /app/docker/gunicorn.conf.py ./docker/gunicorn.conf.py
COPY --from=build --chown=simdb:simdb /app/src/ ./src/

ARG APP_VERSION=0.0.0

LABEL org.opencontainers.image.title="SimDB" \
      org.opencontainers.image.description="SimDB Server — ITER simulation management tool" \
      org.opencontainers.image.source="https://github.com/iterorganization/SimDB" \
      org.opencontainers.image.licenses="LGPL-3.0-only" \
      org.opencontainers.image.version="${APP_VERSION}" \
      io.simdb.component="server"

ENV SIMDB_SITE_CONFIG_PATH=/app/config/simdb.cfg

USER simdb

EXPOSE 5000

# Run under Gunicorn rather than the Werkzeug dev server
CMD ["uv", "run", "gunicorn", "--config=/app/docker/gunicorn.conf.py", "simdb.remote.wsgi:app"]
