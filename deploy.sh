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

# Verify n8n untouched
if docker ps --format '{{.Names}}' | grep -q "^n8n$"; then
    log "n8n: running (untouched)"
fi

# 2. Verify project
if [ ! -f "$APP_DIR/docker-compose.yml" ]; then
    err "Project not found at $APP_DIR. Upload first:\n  scp -r \"C:\\Users\\My PC\\OneDrive\\Documents\\Default Project\\ai-sales-dashboard\" root@2.28.10.88:/opt/ai-sales-dashboard"
fi
log "Project files found."

# 3. Generate all secrets
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
PG_PASS=$(openssl rand -base64 24 | tr -d '\n')
ADMIN_PASS=$(openssl rand -base64 16 | tr -d '\n')
ADMIN_EMAIL="admin@${DOMAIN}"
log "Secrets generated."

# 4. Write env files
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
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
META_APP_SECRET=
META_VERIFY_TOKEN=
META_PAGE_ACCESS_TOKEN=
META_IG_ACCOUNT_ID=
ADMIN_EMAIL=${ADMIN_EMAIL}
ADMIN_PASSWORD=${ADMIN_PASS}
ADMIN_FULL_NAME=Administrator
SENTRY_DSN=
ENVEOF

cat > "$APP_DIR/frontend/.env.production" <<ENVEOF
NEXT_PUBLIC_API_URL=https://api.${DOMAIN}
ENVEOF
log "Environment files written."

# 5. Build and start
cd "$APP_DIR"
docker compose down 2>/dev/null || true
docker compose up -d --build
log "Containers building..."

# 6. Wait for PostgreSQL
for i in $(seq 1 30); do
    docker compose exec -T db pg_isready -U dashboard >/dev/null 2>&1 && { log "PostgreSQL ready."; break; }
    sleep 2
done

# 7. Wait for backend
log "Waiting for backend..."
for i in $(seq 1 60); do
    if curl -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
        log "Backend healthy."
        break
    fi
    [ $i -eq 60 ] && warn "Backend not ready. Check: docker compose logs backend"
    sleep 3
done

# 8. Migrations
log "Running migrations..."
docker compose exec -T backend alembic upgrade head 2>/dev/null || warn "Run manually: docker compose exec backend alembic upgrade head"

# 9. Verify
echo ""
log "=== Verification ==="
curl -sf http://127.0.0.1:8001/health && echo "" || warn "/health failed"
curl -sf http://127.0.0.1:8001/ready && echo "" || warn "/ready failed"
curl -sf http://127.0.0.1:3000 >/dev/null && log "Frontend OK" || warn "Frontend not ready"

# 10. Print results
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "2.28.10.88")

echo ""
echo "============================================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================================"
echo ""
echo "  ADMIN LOGIN:"
echo "    Email:    ${ADMIN_EMAIL}"
echo "    Password: ${ADMIN_PASS}"
echo ""
echo "  (Saved to: $APP_DIR/backend/.env.production)"
echo ""
echo "  Local test:  http://127.0.0.1:3000"
echo "               http://127.0.0.1:8001/docs"
echo ""
echo "  STILL NEEDED:"
echo ""
echo "  1. DNS A records (at your domain registrar):"
echo "       app.eviraw.com    ${SERVER_IP}"
echo "       api.eviraw.com    ${SERVER_IP}"
echo ""
echo "  2. Add to Caddyfile (/etc/caddy/Caddyfile):"
echo ""
cat <<'CADDY'
app.eviraw.com {
    reverse_proxy 127.0.0.1:3000
    header {
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }
}

api.eviraw.com {
    reverse_proxy 127.0.0.1:8001
    header {
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
    }
    handle /webhooks/* {
        reverse_proxy 127.0.0.1:8001
    }
    handle /health {
        reverse_proxy 127.0.0.1:8001
    }
    handle /ready {
        reverse_proxy 127.0.0.1:8001
    }
    handle {
        reverse_proxy 127.0.0.1:8001
    }
}
CADDY
echo ""
echo "  Then run:  systemctl reload caddy"
echo "  (Caddy auto-obtains SSL via Let's Encrypt)"
echo ""
echo "  3. Fill in API keys (edit directly on server):"
echo "       nano $APP_DIR/backend/.env.production"
echo "     Find and fill these lines:"
echo "       OPENAI_API_KEY=..."
echo "       META_APP_SECRET=..."
echo "       META_VERIFY_TOKEN=..."
echo "       META_PAGE_ACCESS_TOKEN=..."
echo "       META_IG_ACCOUNT_ID=..."
echo "     Then: cd $APP_DIR && docker compose restart backend"
echo ""
echo "  4. Meta webhook URL:"
echo "       https://api.eviraw.com/webhooks/meta"
echo "       Verify Token: (the META_VERIFY_TOKEN above)"
echo ""
echo "  Commands:"
echo "    Logs:    cd $APP_DIR && docker compose logs -f"
echo "    Restart: cd $APP_DIR && docker compose restart"
echo "    Stop:    cd $APP_DIR && docker compose down"
echo ""
