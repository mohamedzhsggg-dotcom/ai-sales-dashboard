#!/bin/bash
set -e

echo ""
echo "============================================================"
echo "  AI Sales Dashboard - Linux Deployment Script"
echo "============================================================"
echo ""

# ── Check Docker ──────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "ERROR: Docker is not installed."
    echo "Install with: curl -fsSL https://get.docker.com | sh"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "ERROR: Docker Compose plugin not found."
    echo "Install with: sudo apt-get install docker-compose-plugin"
    exit 1
fi

echo "[OK] Docker $(docker --version | awk '{print $3}') available."
echo ""

# ── Get domain ────────────────────────────────────────────────
read -p "Enter your domain (e.g., raqi-ke.dz): " DOMAIN
if [ -z "$DOMAIN" ]; then
    echo "ERROR: Domain cannot be empty."
    exit 1
fi

echo ""
echo "Domain: $DOMAIN"
echo "  App URL:  https://app.$DOMAIN"
echo "  API URL:  https://api.$DOMAIN"
echo "  n8n URL:  https://n8n.$DOMAIN (existing)"
echo ""

# ── Generate secrets ─────────────────────────────────────────
SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
PG_PASS=$(openssl rand -base64 24 | tr -d '\n')

echo "[OK] Generated secrets."
echo ""

# ── Collect optional secrets ─────────────────────────────────
echo "─────────────────────────────────────────────────────────────"
echo "  SECRETS NEEDED"
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "The following are REQUIRED for full functionality."
echo "You can leave them empty and fill in later."
echo ""

read -p "OpenAI API Key (Enter to skip): " OPENAI_KEY
read -p "Meta App Secret (Enter to skip): " META_SECRET
read -p "Meta Verify Token (Enter to skip): " META_VERIFY
read -p "Meta Page Access Token (Enter to skip): " META_PAGE_TOKEN
read -p "Meta Instagram Account ID (Enter to skip): " META_IG

# ── Write backend .env.production ────────────────────────────
echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  CONFIGURING ENVIRONMENT FILES"
echo "─────────────────────────────────────────────────────────────"
echo ""

cat > backend/.env.production <<ENVEOF
APP_ENV=production
DEBUG=false
SECRET_KEY=${SECRET_KEY}

POSTGRES_USER=dashboard
POSTGRES_PASSWORD=${PG_PASS}
POSTGRES_DB=dashboard
DATABASE_URL=postgresql+psycopg2://dashboard:${PG_PASS}@db:5432/dashboard

REDIS_URL=redis://redis:6379/0

CORS_ORIGINS=["https://app.${DOMAIN}"]

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

TEST_DATABASE_URL=postgresql+psycopg2://dashboard:${PG_PASS}@db:5432/dashboard_test
ENVEOF

# ── Write frontend .env.production ────────────────────────────
cat > frontend/.env.production <<ENVEOF
NEXT_PUBLIC_API_URL=https://api.${DOMAIN}
ENVEOF

echo "[OK] Environment files configured."
echo ""

# ── Create nginx certs directory ──────────────────────────────
mkdir -p nginx/certs

echo "─────────────────────────────────────────────────────────────"
echo "  BUILDING AND STARTING SERVICES"
echo "─────────────────────────────────────────────────────────────"
echo ""

docker compose down 2>/dev/null || true
docker compose up -d --build

echo ""
echo "[OK] Services started."
echo ""

echo "─────────────────────────────────────────────────────────────"
echo "  RUNNING DATABASE MIGRATIONS"
echo "─────────────────────────────────────────────────────────────"
echo ""

sleep 10
docker compose exec backend alembic upgrade head

echo ""
echo "[OK] Migrations applied."
echo ""

echo "─────────────────────────────────────────────────────────────"
echo "  VERIFYING HEALTH"
echo "─────────────────────────────────────────────────────────────"
echo ""

sleep 5
docker compose exec backend python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health'); print('Backend health:', r.read().decode())"

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  DEPLOYMENT COMPLETE"
echo "─────────────────────────────────────────────────────────────"
echo ""
echo "Your services are now running:"
echo ""
echo "  Dashboard: https://app.$DOMAIN"
echo "  API:       https://api.$DOMAIN"
echo "  API Docs:  https://api.$DOMAIN/docs"
echo "  Health:    https://api.$DOMAIN/health"
echo ""
echo "IMPORTANT: You still need to:"
echo ""
echo "  1. Point DNS A records:"
echo "     app.$DOMAIN  -> $(curl -s ifconfig.me 2>/dev/null || echo '<server-ip>')"
echo "     api.$DOMAIN  -> $(curl -s ifconfig.me 2>/dev/null || echo '<server-ip>')"
echo ""
echo "  2. Obtain SSL certificates (Let's Encrypt):"
echo "     sudo apt install certbot"
echo "     sudo certbot certonly --standalone -d app.$DOMAIN -d api.$DOMAIN"
echo "     sudo cp /etc/letsencrypt/live/app.$DOMAIN/fullchain.pem nginx/certs/"
echo "     sudo cp /etc/letsencrypt/live/app.$DOMAIN/privkey.pem nginx/certs/"
echo "     docker compose restart nginx"
echo ""
echo "  3. Fill in any skipped secrets in backend/.env.production"
echo "     then run: docker compose restart backend"
echo ""
echo "  4. Configure Meta webhook URL in Facebook Developer Console:"
echo "     URL: https://api.$DOMAIN/webhooks/meta"
echo "     Verify Token: (the META_VERIFY_TOKEN you set above)"
echo ""
echo "  5. If n8n is on the same server, ensure it's accessible at"
echo "     its existing port. Add to nginx/conf.d/ if needed."
echo ""
echo "To view logs:  docker compose logs -f"
echo "To stop:       docker compose down"
echo "To restart:    docker compose restart"
echo ""
