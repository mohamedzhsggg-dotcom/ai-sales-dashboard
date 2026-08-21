@echo off
REM ============================================================
REM DEPLOYMENT SCRIPT - AI Sales Dashboard
REM ============================================================
REM Run this script on the TARGET SERVER with Docker installed.
REM It will:
REM   1. Verify Docker is available
REM   2. Ask for your domain name
REM   3. Generate secrets
REM   4. Configure environment files
REM   5. Build and start all services
REM   6. Run database migrations
REM   7. Verify health checks
REM ============================================================

echo.
echo ============================================================
echo   AI Sales Dashboard - Deployment Script
echo ============================================================
echo.

REM Check Docker
docker --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker is not installed or not in PATH.
    echo Please install Docker Desktop from https://docker.com/products/docker-desktop
    echo Then run this script again.
    pause
    exit /b 1
)

docker compose version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: Docker Compose is not available.
    echo Please update Docker Desktop to the latest version.
    pause
    exit /b 1
)

echo [OK] Docker is available.
echo.

REM Get domain
set /p DOMAIN="Enter your domain (e.g., raqi-ke.dz): "
if "%DOMAIN%"=="" (
    echo ERROR: Domain cannot be empty.
    pause
    exit /b 1
)

echo.
echo Domain: %DOMAIN%
echo   App URL:  https://app.%DOMAIN%
echo   API URL:  https://api.%DOMAIN%
echo   n8n URL:  https://n8n.%DOMAIN% (existing)
echo.

REM Generate SECRET_KEY
for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(48))" 2>nul || echo %RANDOM%%RANDOM%%RANDOM%%RANDOM%%RANDOM%%RANDOM%') do set SECRET_KEY=%%i

if "%SECRET_KEY%"=="" (
    echo ERROR: Could not generate SECRET_KEY. Make sure Python is installed.
    pause
    exit /b 1
)

echo [OK] Generated SECRET_KEY.
echo.

REM Generate POSTGRES_PASSWORD
for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(24))" 2>nul || echo %RANDOM%%RANDOM%%RANDOM%') do set PG_PASS=%%i

echo [OK] Generated database password.
echo.

REM Ask for missing secrets
echo ─────────────────────────────────────────────────────────────
echo   SECRETS NEEDED
echo ─────────────────────────────────────────────────────────────
echo.
echo The following secrets are REQUIRED for full functionality.
echo You can leave them empty for now and fill them in later.
echo.

set /p OPENAI_KEY="OpenAI API Key (or press Enter to skip): "
set /p META_SECRET="Meta App Secret (or press Enter to skip): "
set /p META_VERIFY="Meta Verify Token (or press Enter to skip): "
set /p META_PAGE_TOKEN="Meta Page Access Token (or press Enter to skip): "
set /p META_IG="Meta Instagram Account ID (or press Enter to skip): "

echo.
echo ─────────────────────────────────────────────────────────────
echo   CONFIGURING ENVIRONMENT FILES
echo ─────────────────────────────────────────────────────────────
echo.

REM Backend .env.production
(
echo APP_ENV=production
echo DEBUG=false
echo SECRET_KEY=%SECRET_KEY%
echo.
echo POSTGRES_USER=dashboard
echo POSTGRES_PASSWORD=%PG_PASS%
echo POSTGRES_DB=dashboard
echo DATABASE_URL=postgresql+psycopg2://dashboard:%PG_PASS%@db:5432/dashboard
echo.
echo REDIS_URL=redis://redis:6379/0
echo.
echo CORS_ORIGINS=["https://app.%DOMAIN%"]
echo.
echo RATE_LIMIT_ENABLED=true
echo RATE_LIMIT_PER_MINUTE=120
echo RATE_LIMIT_AUTH_PER_MINUTE=20
echo.
echo SHEETS_COMPAT_MODE=false
echo.
echo STORAGE_BACKEND=local
echo STORAGE_LOCAL_DIR=storage/media
echo.
echo DEFAULT_FROM_WILAYA=Alger
echo YALIDINE_API_BASE_URL=https://api.yalidine.app/v1
echo.
echo RETURNS_ENABLED=true
echo SHIPMENTS_ENABLED=true
echo.
echo AI_PROVIDER=mock
echo OPENAI_API_KEY=%OPENAI_KEY%
echo OPENAI_MODEL=gpt-4o-mini
echo.
echo META_APP_SECRET=%META_SECRET%
echo META_VERIFY_TOKEN=%META_VERIFY%
echo META_PAGE_ACCESS_TOKEN=%META_PAGE_TOKEN%
echo META_IG_ACCOUNT_ID=%META_IG%
echo.
echo SENTRY_DSN=
echo.
echo TEST_DATABASE_URL=postgresql+psycopg2://dashboard:%PG_PASS%@db:5432/dashboard_test
) > backend\.env.production

REM Frontend .env.production
(
echo NEXT_PUBLIC_API_URL=https://api.%DOMAIN%
) > frontend\.env.production

echo [OK] Environment files configured.
echo.

echo ─────────────────────────────────────────────────────────────
echo   BUILDING AND STARTING SERVICES
echo ─────────────────────────────────────────────────────────────
echo.

REM Stop any existing containers
docker compose down 2>nul

REM Build and start
docker compose up -d --build

echo.
echo [OK] Services started.
echo.

echo ─────────────────────────────────────────────────────────────
echo   RUNNING DATABASE MIGRATIONS
echo ─────────────────────────────────────────────────────────────
echo.

docker compose exec backend alembic upgrade head

echo.
echo [OK] Migrations applied.
echo.

echo ─────────────────────────────────────────────────────────────
echo   VERIFYING HEALTH
echo ─────────────────────────────────────────────────────────────
echo.

timeout /t 10 /nobreak >nul

docker compose exec backend python -c "import urllib.request; r=urllib.request.urlopen('http://localhost:8000/health'); print('Backend health:', r.read().decode())"

echo.
echo ─────────────────────────────────────────────────────────────
echo   DEPLOYMENT COMPLETE
echo ─────────────────────────────────────────────────────────────
echo.
echo Your services are now running:
echo.
echo   Dashboard: https://app.%DOMAIN%
echo   API:       https://api.%DOMAIN%
echo   API Docs:  https://api.%DOMAIN%/docs
echo   Health:    https://api.%DOMAIN%/health
echo.
echo IMPORTANT: You still need to:
echo.
echo   1. Point DNS A records:
echo      app.%DOMAIN%  -> %DOMAIN% server IP
echo      api.%DOMAIN%  -> %DOMAIN% server IP
echo.
echo   2. Obtain SSL certificates (Let's Encrypt):
echo      Place files in nginx/certs/fullchain.pem
echo      and nginx/certs/privkey.pem
echo.
echo   3. Fill in any skipped secrets in backend\.env.production
echo      then run: docker compose restart backend
echo.
echo   4. Configure Meta webhook URL in Facebook Developer Console:
echo      URL: https://api.%DOMAIN%/webhooks/meta
echo      Verify Token: (the META_VERIFY_TOKEN you set above)
echo.
echo To view logs: docker compose logs -f
echo To stop:      docker compose down
echo.
pause
