#!/usr/bin/env bash
#
# Helpers shared by postgres-backup and postgres-restore.

# Print the id of the running container of a compose project and service.
container_id_for_project_and_service() {
    local project="$1" service="$2" ids

    ids="$(
        docker ps -q \
            --filter "label=com.docker.compose.project=$project" \
            --filter "label=com.docker.compose.service=$service"
    )" || {
        echo "could not query docker for service $service of project $project" >&2
        return 1
    }
    ids="${ids%%$'\n'*}"
    [[ -n "$ids" ]] || {
        echo "no running $service container for compose project: $project" >&2
        return 1
    }
    printf '%s\n' "$ids"
}

# Inspect a container and set container_id, image, compose_project,
# compose_service, working_dir, config_files, POSTGRES_USER and POSTGRES_DB.
load_container_metadata() {
    local inspect_id="$1" line meta

    meta="$(
        docker inspect --format 'container_id={{.Id}}
image={{.Config.Image}}
compose_project={{index .Config.Labels "com.docker.compose.project"}}
compose_service={{index .Config.Labels "com.docker.compose.service"}}
working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}}
config_files={{index .Config.Labels "com.docker.compose.project.config_files"}}
{{range .Config.Env}}{{println .}}{{end}}' "$inspect_id"
    )" || {
        echo "could not inspect container: $inspect_id" >&2
        return 1
    }

    image=
    compose_project=
    compose_service=
    working_dir=
    config_files=
    while IFS= read -r line; do
        case "$line" in
            container_id=*) container_id="${line#container_id=}" ;;
            image=*) image="${line#image=}" ;;
            compose_project=*) compose_project="${line#compose_project=}" ;;
            compose_service=*) compose_service="${line#compose_service=}" ;;
            working_dir=*) working_dir="${line#working_dir=}" ;;
            config_files=*) config_files="${line#config_files=}" ;;
            POSTGRES_USER=*) POSTGRES_USER="${POSTGRES_USER:-${line#POSTGRES_USER=}}" ;;
            POSTGRES_DB=*) POSTGRES_DB="${POSTGRES_DB:-${line#POSTGRES_DB=}}" ;;
        esac
    done <<<"$meta"

    [[ -n "$compose_project" ]] || {
        echo "container has no compose project label: $inspect_id" >&2
        return 1
    }

    POSTGRES_USER="${POSTGRES_USER:-simdb}"
    POSTGRES_DB="${POSTGRES_DB:-simdb}"
}

# Print the selected container and database to stderr.
print_container_selection() {
    printf 'container:    %s\n' "$container_id" >&2
    printf 'image:        %s\n' "$image" >&2
    printf 'project:      %s (service %s)\n' "$compose_project" "$compose_service" >&2
    printf 'working dir:  %s\n' "$working_dir" >&2
    printf 'config files: %s\n' "$config_files" >&2
    printf 'database:     %s (role %s)\n' "$POSTGRES_DB" "$POSTGRES_USER" >&2
}