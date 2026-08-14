#!/usr/bin/env bash
#
# RouteForge backup script.
#
# Backs up PostgreSQL (logical dump) and Redis (RDB snapshot) from the
# docker-compose services and prunes old backups.
#
# Usage:
#   ./scripts/backup.sh                      # full backup of both services
#   ./scripts/backup.sh --db-only            # PostgreSQL only
#   ./scripts/backup.sh --redis-only        # Redis only
#   ./scripts/backup.sh --retention 14      # keep 14 backups (default 7)
#
# Environment:
#   BACKUP_DIR        output directory (default ./backups)
#   REDIS_PASSWORD    Redis requirepass, if configured
#   POSTGRES_PASSWORD PostgreSQL password (default postgres)
#
# Restore instructions: see docs/DISASTER_RECOVERY.md

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$SCRIPT_DIR/../backups}"
RETENTION=7
MODE="all"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-only) MODE="db" ;;
    --redis-only) MODE="redis" ;;
    --retention) RETENTION="$2"; shift ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

mkdir -p "$BACKUP_DIR"
TS="$(date +%Y%m%d-%H%M%S)"

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

backup_db() {
  local out="$BACKUP_DIR/vrp-db-$TS.sql.gz"
  log "Backing up PostgreSQL -> $out"
  docker exec vrp-postgres pg_dump -U postgres -d vrp \
    --format=custom \
    | gzip -1 > "$out"
  log "PostgreSQL backup complete"
}

backup_redis() {
  local out="$BACKUP_DIR/vrp-redis-$TS.rdb.gz"
  log "Backing up Redis -> $out"
  docker exec vrp-redis redis-cli ${REDIS_PASSWORD:+-a "$REDIS_PASSWORD"} BGSAVE > /dev/null
  sleep 2
  docker exec vrp-redis sh -c 'cat /data/dump.rdb' | gzip -1 > "$out"
  log "Redis backup complete"
}

prune() {
  log "Pruning backups older than $RETENTION days"
  find "$BACKUP_DIR" -type f -name 'vrp-*.gz' -mtime "+$RETENTION" -delete
}

case "$MODE" in
  all)
    backup_db
    backup_redis
    ;;
  db)
    backup_db
    ;;
  redis)
    backup_redis
    ;;
esac

prune
log "Backup finished -> $BACKUP_DIR"
