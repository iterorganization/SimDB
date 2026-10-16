#!/bin/sh
# Use gosu in this entrypoint instead of USER in Dockerfile:
# - USER is fixed at build time and cannot adapt to host-specific APP_UID/APP_GID at runtime
# - Container should start as root to create the matching unprivileged user in the container
# - Finally, gosu cleanly execs the app as the unprivileged user without keeping a root shell around

set -eu

# Use APP_ prefix for in-container environment vars. 
app_uid=${APP_UID:-1000}
app_gid=${APP_GID:-1000}

# Unlike the APP_UID and APP_GID above, these APP_* variables should not need changing.
app_user=${APP_USER:-simdb}
app_group=${APP_GROUP:-simdb}
app_home=${APP_HOME:-/home/simdb}
app_data_dir=${APP_DATA_DIR:-/data/simdb/simulations}

if ! command -v gosu >/dev/null 2>&1; then
    echo "gosu is required but not installed" >&2
    exit 1
fi

# Typically, UID and GID are non-existent in a blank OS image

if getent group "${app_gid}" >/dev/null 2>&1; then
    echo "group id ${app_gid} already exists" >&2
else
    groupadd --gid "${app_gid}" "${app_group}"
fi

if getent passwd "${app_uid}" >/dev/null 2>&1; then
    echo "user id ${app_uid} already exists" >&2
else
    useradd \
        --uid "${app_uid}" \
        --gid "${app_gid}" \
        --home-dir "${app_home}" \
        --create-home \
        --shell /usr/sbin/nologin \
        "${app_user}"
fi

# mkdir just in case docker-compose didnt:
mkdir -p "${app_data_dir}"

if ! gosu "${app_user}" test -w "${app_data_dir}"; then
    echo "${app_data_dir} is not writable by ${app_uid}:${app_gid}" >&2
    ls -ldn "${app_data_dir}" >&2 || true
    exit 1
fi

export HOME="${app_home}"
export USER="${app_user}"
export LOGNAME="${app_user}"

exec gosu "${app_user}" "$@"