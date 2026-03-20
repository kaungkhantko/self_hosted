#!/usr/bin/env bash
# run.sh — CLI entrypoint for self_hosted stack
# Usage: ./run.sh <command> [args]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO_ROOT}"

# Load .env if it exists (for COMPOSE_FILE support)
if [[ -f .env ]]; then
  set -a; source .env; set +a
fi

CMD="${1:-help}"

case "${CMD}" in
  bootstrap)
    ## First-run: env check, dirs, systemd, pull, up, seed *arr
    bash scripts/bootstrap.sh
    ;;
  up)
    ## Start the stack
    docker compose up -d
    ;;
  down)
    ## Stop the stack
    docker compose down
    ;;
  restart)
    ## Stop then start the stack
    docker compose down
    docker compose up -d
    ;;
  logs)
    ## Follow logs — optionally pass a service name
    ## Usage: ./run.sh logs [service]
    shift
    docker compose logs -f "$@"
    ;;
  pull)
    ## Pull latest images via scripts/pull-images.sh
    bash scripts/pull-images.sh
    ;;
  update)
    ## Pull latest images then restart with orphan cleanup
    bash scripts/pull-images.sh
    docker compose up -d --remove-orphans
    ;;
  status)
    ## Show running containers
    docker compose ps
    ;;
  help|--help|-h|"")
    echo ""
    echo "  self_hosted — run.sh command reference"
    echo ""
    echo "  Usage: ./run.sh <command> [args]"
    echo ""
    echo "  Commands:"
    echo "    bootstrap          First-run setup: env, dirs, systemd, seed *arr"
    echo "    up                 Start the stack (docker compose up -d)"
    echo "    down               Stop the stack"
    echo "    restart            Stop then start"
    echo "    logs [service]     Follow logs (all services, or a named one)"
    echo "    pull               Pull latest images"
    echo "    update             Pull + restart with orphan cleanup"
    echo "    status             Show running containers"
    echo "    help               Show this message"
    echo ""
    ;;
  *)
    echo "Unknown command: ${CMD}"
    echo "Run ./run.sh help for usage."
    exit 1
    ;;
esac
