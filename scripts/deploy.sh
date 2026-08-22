#!/usr/bin/env bash
# Blue-green deploy for the VRP logistics stack.
#
# Usage:
#   scripts/deploy.sh [IMAGE_TAG]
#
# Environment (all required on the server):
#   REDIS_PASSWORD     Shared Redis password (also in .env.production)
#   POSTGRES_PASSWORD  Shared Postgres password (also in .env.production)
#
# Strategy:
#   1. Ensure shared infra (redis/postgres) is up.
#   2. Determine the active color (blue/green) from a state file.
#   3. Pull + start the INACTIVE color with the new image tag.
#   4. Run alembic migrations inside the new backend container.
#   5. Health-check the new backend through the shared network.
#   6. Flip the router to the new color, then stop the old color.
#   7. On any failure, leave the active stack untouched and exit non-zero.

set -euo pipefail

IMAGE_TAG="${1:-latest}"
STATE_FILE="${STATE_FILE:-/var/lib/vrp/active-color}"
ROUTER_TEMPLATE="deploy/router/router.conf.template"
ROUTER_CONF="deploy/router/router.conf"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_ARGS=(-f docker-compose.infra.yml -f docker-compose.prod.yml)

cd "$PROJECT_ROOT"

log() { printf '[deploy] %s\n' "$*"; }
fail() { printf '[deploy] ERROR: %s\n' "$*" >&2; exit 1; }

# ── 1. Shared infrastructure ────────────────────────────────────────────────
log "Ensuring shared infra is up"
docker compose -p vrp-infra -f docker-compose.infra.yml up -d

# ── 2. Determine colors ─────────────────────────────────────────────────────
ACTIVE="$(cat "$STATE_FILE" 2>/dev/null || echo blue)"
case "$ACTIVE" in
  blue) NEW="green" ;;
  green) NEW="blue" ;;
  *) fail "unknown active color '$ACTIVE' in $STATE_FILE" ;;
esac
log "active=$ACTIVE -> deploying $NEW with tag $IMAGE_TAG"

# ── 3. Start the new (inactive) color ───────────────────────────────────────
if docker compose -p "vrp-$NEW" -f docker-compose.prod.yml ps >/dev/null 2>&1 &&
   docker compose -p "vrp-$NEW" -f docker-compose.prod.yml ps --status running -q | grep -q .; then
  log "Old $NEW stack still running; stopping it first"
  docker compose -p "vrp-$NEW" -f docker-compose.prod.yml down || true
fi

log "Starting $NEW stack"
IMAGE_TAG="$IMAGE_TAG" COLOR="$NEW" docker compose -p "vrp-$NEW" \
  -f docker-compose.prod.yml up -d --pull always

# ── 4. Migrations ───────────────────────────────────────────────────────────
log "Running migrations on $NEW"
docker compose -p "vrp-$NEW" -f docker-compose.prod.yml exec -T backend \
  alembic upgrade head

# ── 5. Health check ─────────────────────────────────────────────────────────
log "Health-checking $NEW backend"
HEALTHY=0
for i in $(seq 1 30); do
  if docker compose -p "vrp-$NEW" -f docker-compose.prod.yml exec -T backend \
      python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/health',timeout=5)" >/dev/null 2>&1; then
    HEALTHY=1
    break
  fi
  log "  waiting for $NEW backend (${i}/30)"
  sleep 5
done
[ "$HEALTHY" = "1" ] || fail "$NEW stack failed health check; keeping $ACTIVE active"

# ── 6. Flip router + stop old color ─────────────────────────────────────────
log "Flipping router to $NEW"
sed "s/__FRONTEND_SERVICE__/vrp-frontend-${NEW}/" "$ROUTER_TEMPLATE" > "$ROUTER_CONF"
docker compose -p vrp-router -f docker-compose.router.yml up -d --force-recreate

log "Stopping old $ACTIVE stack"
docker compose -p "vrp-$ACTIVE" -f docker-compose.prod.yml down || true

echo "$NEW" > "$STATE_FILE"
log "Deploy complete: $NEW active ($IMAGE_TAG)"
