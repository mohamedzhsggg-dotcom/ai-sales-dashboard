#!/bin/bash
set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log()  { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

APP_DIR="/opt/ai-sales-dashboard"
DOMAIN="eviraw.com"

echo ""
echo "============================================================"
echo "  AI Sales Dashboard - Deployment for $DOMAIN"
echo "  n8n will NOT be modified."
echo "============================================================"
echo ""

# 1. Pre-flight
if [ "$EUID" -ne 0 ]; then err "Run as root: sudo bash deploy.sh"; fi
docker --version >/dev/null 2>&1 || err "Docker not installed"
if ! docker compose version >/dev/null 2>&1; then
    warn "Installing Docker Compose plugin..."
    apt-get update -qq && apt-get install -y -qq docker-compose-plugin
fi
log "Docker: $(docker --version 2>&1 | head -1)"
log "Compose: $(docker compose version 2>&1 | head -1)"
if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
    log "n8n: running (untouched)"
fi

# 2. Verify project
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    err "Project not found at $APP_DIR"
fi
log "Project files found."

# 3. Generate secrets
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
PG_PASS=$(openssl rand -base64 24 | tr -d '\n')
log "Secrets generated."

# 4. Collect credentials
echo ""
echo "  Press Enter to skip any credential."
echo ""
read -p "  OpenAI API Key (Enter to skip): " OPENAI_KEY
read -p "  Meta App Secret (Enter to skip): " META_SECRET
read -p "  Meta Verify Token (Enter to skip): " META_VERIFY
read -p "  Meta Page Access Token (Enter to skip): " META_PAGE_TOKEN
read -p "  Meta Instagram Account ID (Enter to skip): " META_IG

# 5. Write env files
cat > "$APP_DIR/backend/.env.production" <<ENVEOF
APP_ENV=production
DEBUG=false
SECRET_KEY=${SECRET_KEY}
POSTGRES_USER=dashboard
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=dashboard
DATABASE_URL=postgresql+psycopg2://dashboard:${PG_PASS}@db:5432/dashboard
REDIS_URL=redis://redis:6379/0
CORS_ORIGINS=["https://app.${DOMAIN}","https://${DOMAIN}"]
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=120
RATE_LIMIT_AUTH_PER_MINUTE=20
SHEETS_COMPAT_MODE=false
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=storage/media
DEFAULT_FROM_WILAYA=Alger
YALIDINE_API_BASE_URL=https://api.yalidine.app/v1
RETURNS_ENABLED=true
SHIPMENTS_ENABLED=true
AI_PROVIDER=mock
OPENAI_API_KEY=${OPENAI_KEY}
OPENAI_MODEL=gpt-4o-mini
META_APP_SECRET=${META_SECRET}
META_VERIFY_TOKEN=${META_VERIFY}
META_PAGE_ACCESS_TOKEN=${META_PAGE_TOKEN}
META_IG_ACCOUNT_ID=${META_IG}
SENTRY_DSN=
ENVEOF

cat > "$APP_DIR/frontend/.env.production" <<ENVEOF
NEXT_PUBLIC_API_URL=https://api.${DOMAIN}
ENVEOF
log "Env files written."

# 6. Build and start
cd "$APP_DIR"
docker compose down 2>/dev/null || true
docker compose up -d --build
log "Containers building..."

# 7. Wait for PostgreSQL
for i in $(seq 1 30); do
    docker compose exec -T db pg_isready -U dashboard >/dev/null 2>&1 && { log "PostgreSQL ready."; break; }
    sleep 2
done

# 8. Wait for backend
log "Waiting for backend..."
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
        log "Backend healthy."
        break
    fi
    [ $i -eq 60 ] && warn "Backend not ready. Check: docker compose logs backend"
    sleep 3
done

# 9. Migrations
log "Running migrations..."
docker compose exec -T backend alembic upgrade head 2>/dev/null || warn "Run manually: docker compose exec backend alembic upgrade head"

# 10. Verify
echo ""
log "=== Verification ==="
curl -sf http://127.0.0.1:8001/health && echo "" || warn "/health failed"
curl -sf http://127.0.0.1:8001/ready && echo "" || warn "/ready failed"
curl -sf http://127.0.0.1:3000 >/dev/null && log "Frontend OK" || warn "Frontend not ready"

# 11. Caddy config
echo ""
echo "============================================================"
echo "  ADD TO CADDYFILE (/etc/caddy/Caddyfile)"
echo "============================================================"
echo ""
echo "# --- AI Sales Dashboard ---"
echo "app.eviraw.com {"
echo "    reverse_proxy 127.0.0.1:3000"
echo "    header { X-Frame-Options SAMEORIGIN X-Content-Type-Options nosniff Strict-Transport-Security max-age=31536000;includeSubDomains }"
echo "}"
echo ""
echo "api.eviraw.com {"
echo "    reverse_proxy 127.0.0.1:8001"
echo "    header { X-Frame-Options DENY X-Content-Type-Options nosniff Strict-Transport-Security max-age=31536000;includeSubDomains }"
echo "}"
echo "# --- END AI Sales Dashboard ---"
echo ""
echo "Then run: sudo systemctl reload caddy"
echo ""

echo "============================================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo "  Local test:  http://127.0.0.1:3000 (dashboard)"
echo "               http://127.0.0.1:8001 (API)"
echo ""
echo "  STILL NEEDED:"
echo "    1. DNS: app.eviraw.com -> $(curl -s ifconfig.me)"
echo "           api.eviraw.com -> $(curl -s ifconfig.me)"
echo "    2. Add Caddy config above to /etc/caddy/Caddyfile"
echo "    3. sudo systemctl reload caddy"
echo "    4. Fill skipped secrets:"
echo "       nano $APP_DIR/backend/.env.production"
echo "       cd $APP_DIR && docker compose restart backend"
echo "    5. Meta webhook: https://api.eviraw.com/webhooks/meta"
echo ""
echo "  Commands:"
echo "    Logs:    cd $APP_DIR && docker compose logs -f"
echo "    Restart: cd $APP_DIR && docker compose restart"
echo "    Stop:    cd $APP_DIR && docker compose down"
echo ""
