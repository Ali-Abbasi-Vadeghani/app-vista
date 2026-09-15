set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

ENV_FILE=".env"
ENV_EXAMPLE=".env.example"
COMPOSE_FILE="docker-compose.yml"

log()   { printf "\033[1;34m[appvista]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[appvista]\033[0m %s\n" "$*"; }
error() { printf "\033[1;31m[appvista]\033[0m %s\n" "$*" >&2; }
die()   { error "$*"; exit 1; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || die "Required command not found: $1"
}

preflight() {
    log "Checking required tooling..."
    require_cmd docker
    require_cmd git

    if ! docker compose version >/dev/null 2>&1; then
        die "docker compose (v2 plugin) is not available."
    fi

    if ! docker info >/dev/null 2>&1; then
        die "Docker daemon is not running."
    fi

    [ -f "$COMPOSE_FILE" ] || die "Missing $COMPOSE_FILE in $ROOT_DIR"
    log "All prerequisites satisfied."
}

ensure_env() {
    if [ ! -f "$ENV_FILE" ]; then
        if [ -f "$ENV_EXAMPLE" ]; then
            log "Creating $ENV_FILE from $ENV_EXAMPLE"
            cp "$ENV_EXAMPLE" "$ENV_FILE"
            warn "Review $ENV_FILE and change default credentials."
        else
            warn "$ENV_FILE not found; using compose defaults."
        fi
    else
        log "$ENV_FILE already present."
    fi
}

cmd_up() {
    preflight
    ensure_env
    log "Building and starting all services..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
    cmd_status
    cmd_urls
}

cmd_down() {
    log "Stopping all services (data volumes are preserved)..."
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down
    log "All services stopped."
}

cmd_status() {
    log "Service status:"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
}

cmd_logs() {
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs -f --tail=100
}

cmd_test() {
    preflight
    ensure_env

    local services=("api" "crawler" "storage" "network-analyzer" "metabase")
    local failed=()

    for service in "${services[@]}"; do
        log "Testing service: $service"
        if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" \
            run --rm --no-deps --entrypoint "python -m pytest" "$service" -v; then
            log "$service: passed"
        else
            error "$service: failed"
            failed+=("$service")
        fi
        echo
    done

    if [ ${#failed[@]} -eq 0 ]; then
        log "All service tests passed."
    else
        die "Failed services: ${failed[*]}"
    fi
}

cmd_urls() {
    cat <<'EOF'

  ──────────────────────────────────────────────────────────
  AppVista is up. Access points:
  ──────────────────────────────────────────────────────────
    API ................ http://localhost:8000
    API docs ........... http://localhost:8000/docs
    Network Analyzer ... http://localhost:8010
    Metabase ........... http://localhost:3000
  ──────────────────────────────────────────────────────────

  Useful commands:
    bash setup.sh --status   # show service status
    bash setup.sh --logs     # follow logs
    bash setup.sh --down     # stop (keep data)
    bash setup.sh --test     # run all service tests

  This script never deletes data volumes.

EOF
}

case "${1:-}" in
    ""|--up|up)       cmd_up ;;
    --down|down)      cmd_down ;;
    --status|status)  cmd_status ;;
    --logs|logs)      cmd_logs ;;
    --test|test)      cmd_test ;;
    -h|--help|help)
        cat <<EOF
AppVista setup script

Usage:
  bash setup.sh [command]

Commands:
  (none)|--up       Build and start the full stack (default)
  --down            Stop all services, keep volumes
  --status          Show current service status
  --logs            Follow service logs
  --test            Run unit tests for all services
  --help            Show this help
EOF
        ;;
    *)
        die "Unknown command: $1"
        ;;
esac