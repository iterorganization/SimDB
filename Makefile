# Build and deploy the SimDB server as a systemd service.
#
# Two ways it is used:
#   * `make service` / `make up`  — build / run the compose stack locally.
#   * `sudo make systemd-install` — install the compose files, config and unit
#     file onto the host, then drive the service with `systemctl`.
#
# Variables can be overridden on the command line, e.g.:
#   * Stage an installation under a prefix instead of installing under /
#     (useful for packaging): make systemd-install DESTDIR=/tmp/simdb-staging
#   * Run the locally built image (make service) instead of the published one
#     (ghcr.io/iterorganization/simdb-server:latest):
#     make up SIMDB_IMAGE=simdb-server SIMDB_TAG=service

SHELL := /bin/sh

# APP_VERSION is baked into the image; derive a PEP 440 version from git.
# The same script is run by CI (.github/workflows/docker_image.yml):
APP_VERSION := $(shell sh docker/version.sh pep440)
SETUPTOOLS_SCM_OVERRIDES_FOR_IMAS_SIMDB := '{local_scheme = "no-local-version-strict"}'
APP_UID ?= 1000
APP_GID ?= 1000

SIMDB_PROJECT_NAME ?= simdb-server
COMPOSE_PROJECT_NAME ?= $(SIMDB_PROJECT_NAME)

SIMDB_IMAGE ?= simdb-server
SIMDB_TAG ?= service

# Base compose file first, then the systemd override on top.
COMPOSE_FILE ?= docker-compose.yml:docker-compose.systemd.yml

# Export the compose inputs so the `docker compose` process sees them (and the
# `make list` filters see COMPOSE_PROJECT_NAME). That name matches the
# directory-derived one the systemd unit gets when it runs compose from
# /opt/$(SIMDB_PROJECT_NAME).
export APP_VERSION SIMDB_IMAGE SIMDB_TAG COMPOSE_FILE COMPOSE_PROJECT_NAME

DOCKER_CMD ?= docker
DOCKER_BUILD ?= $(DOCKER_CMD) build \
	--build-arg APP_VERSION="$(APP_VERSION)" \
	--build-arg APP_UID="$(APP_UID)" \
	--build-arg APP_GID="$(APP_GID)"
DOCKER_COMPOSE ?= $(DOCKER_CMD) compose

DOCKER_BUILD_TAG := $(SIMDB_IMAGE):$(SIMDB_TAG)

# Destinations used by systemd-install/systemd-uninstall (DESTDIR for packaging).
package_optdir ?= /opt/$(SIMDB_PROJECT_NAME)
package_etcdir ?= /etc/$(SIMDB_PROJECT_NAME)
systemd_unitdir ?= /etc/systemd/system

.DEFAULT_GOAL := service

.PHONY: \
	down \
	help \
	list \
	list-all \
	logs-f \
	service \
	shell \
	systemd-daemon-reload \
	systemd-disable \
	systemd-enable \
	systemd-install \
	systemd-installdirs \
	systemd-start \
	systemd-status \
	systemd-stop \
	systemd-uninstall \
	up

help:
	@echo "Build and run:"
	@echo "  make service        Build and tag the service image ($(DOCKER_BUILD_TAG))"
	@echo "  make up             Start the stack from the configured image"
	@echo "  make down           Stop the stack"
	@echo ""
	@echo "  make list           List the web container for this compose project"
	@echo "  make list-all       List all containers for this compose project"
	@echo "  make logs-f         Follow the web container's logs"
	@echo "  make shell          Open a shell in the web container"
	@echo ""
	@echo "  SIMDB_IMAGE=simdb-server SIMDB_TAG=service make up"
	@echo "                      Run the image built by 'make service' instead of the published one"
	@echo ""
	@echo "Systemd (run with sudo; see docs/how-to/operate-server/install-server.md):"
	@echo "  sudo make systemd-install       Install files under $(package_optdir) and $(package_etcdir)"
	@echo "  sudo make systemd-enable        systemctl daemon-reload && systemctl enable $(SIMDB_PROJECT_NAME)"
	@echo "  sudo make systemd-start         systemctl start $(SIMDB_PROJECT_NAME)"
	@echo "  sudo make systemd-status        systemctl status $(SIMDB_PROJECT_NAME)"
	@echo "  sudo make systemd-stop          systemctl stop $(SIMDB_PROJECT_NAME)"
	@echo "  sudo make systemd-disable       systemctl stop && systemctl disable $(SIMDB_PROJECT_NAME)"
	@echo "  sudo make systemd-uninstall     Remove everything systemd-install created"

service:
	$(DOCKER_BUILD) --target service -t $(DOCKER_BUILD_TAG) .

# --- compose ---------------------------------------------------------------

up:
	$(DOCKER_COMPOSE) --profile with_workers up -d --no-build

down:
	$(DOCKER_COMPOSE) --profile with_workers down

list:
	$(DOCKER_CMD) ps \
		--filter "label=com.docker.compose.project=$(COMPOSE_PROJECT_NAME)" \
		--filter "label=com.docker.compose.service=web"

list-all:
	$(DOCKER_CMD) ps \
		--filter "label=com.docker.compose.project=$(COMPOSE_PROJECT_NAME)"

logs-f:
	$(DOCKER_COMPOSE) logs -f web

shell:
	$(DOCKER_COMPOSE) exec web sh

# --- systemd integration (run with sudo) -----------------------------------
#
# The service unit runs `docker compose` from $(package_optdir), which is why
# the compose files, the config and validation data are copied there rather
# than bind-mounted from the source tree.

systemd-installdirs:
	mkdir -p \
		$(DESTDIR)$(package_optdir)/config \
		$(DESTDIR)$(package_optdir)/validation \
		$(DESTDIR)$(package_optdir)/tmp/partition_data \
		$(DESTDIR)$(package_etcdir) \
		$(DESTDIR)$(systemd_unitdir)
	install -d -m 0775 -o $(APP_UID) -g $(APP_GID) \
		$(DESTDIR)$(package_optdir)/upload_folder

systemd-install: systemd-installdirs
	install -m 644 \
		docker-compose.yml \
		docker-compose.systemd.yml \
		$(DESTDIR)$(package_optdir)
	install -m 644 \
		config/simdb.cfg \
		$(DESTDIR)$(package_optdir)/config
	install -m 644 \
		validation/iter_scenarios_validation.yaml \
		$(DESTDIR)$(package_optdir)/validation
	install -m 644 \
		docker/scripts/simdb-server.service \
		$(DESTDIR)$(systemd_unitdir)/$(SIMDB_PROJECT_NAME).service
	install -m 644 \
		docker/scripts/simdb-server.env.example \
		"$(DESTDIR)$(package_etcdir)/$(SIMDB_PROJECT_NAME).env.example"
	@if [ ! -f "$(DESTDIR)$(package_etcdir)/$(SIMDB_PROJECT_NAME).env" ]; then \
		install -m 644 docker/scripts/simdb-server.env.example \
			"$(DESTDIR)$(package_etcdir)/$(SIMDB_PROJECT_NAME).env"; \
	fi

systemd-uninstall: systemd-disable
	@printf 'Remove $(DESTDIR)$(package_optdir) and $(DESTDIR)$(package_etcdir)? [y/N] '; \
		read ans; case "$$ans" in [yY]*) ;; *) echo "aborted"; exit 1;; esac
	-rm -f "$(DESTDIR)$(systemd_unitdir)/$(SIMDB_PROJECT_NAME).service"
	-rm -rf "$(DESTDIR)$(package_etcdir)"
	-rm -rf "$(DESTDIR)$(package_optdir)"

systemd-daemon-reload:
	systemctl daemon-reload

systemd-enable: systemd-daemon-reload
	systemctl enable $(SIMDB_PROJECT_NAME)

systemd-disable: systemd-stop
	systemctl disable $(SIMDB_PROJECT_NAME)

systemd-start systemd-status systemd-stop:
	-systemctl $(patsubst systemd-%,%,$@) $(SIMDB_PROJECT_NAME)
