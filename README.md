# AI Sales Dashboard

A professional web dashboard layered on top of the existing **n8n + Google Sheets** production system. It reads and writes the same Google Sheets that the n8n AI agent uses, **without modifying the n8n workflow**.

## Architecture (Phase 1)

```
Facebook/Instagram ──> n8n (unchanged) ──> Google Sheets (source of truth)
                                                  │
                    Sync worker (sheets → Postgres)
                                                  ▼
                                        PostgreSQL (read model + app DB)
                                                  │
                                        FastAPI REST API (JWT auth)
                                                  │
                                        Next.js responsive dashboard
```

- **Google Sheets = system of record.** n8n keeps writing/reading it exactly as today.
- **PostgreSQL = fast indexed read-model** + users/sessions/audit inventory events.
- **Sync worker** polls the 3 sheets, detects changes by content-hash, upserts into Postgres.
- **Write-back service** pushes dashboard changes (status, stock) back to the sheets — serialized and idempotent, no collision with n8n.
- **Confirm Order** transactionally sets status to `confirmed` and deducts inventory in both Postgres and the Product sheet.

## Layout

```
ai-sales-dashboard/
├── backend/            FastAPI app
│   ├── app/
│   │   ├── api/routes/   auth, orders, customers, products, inventory, dashboard, audit
│   │   ├── core/         JWT security
│   │   ├── models/       SQLAlchemy models (tenant-scoped)
│   │   ├── schemas/      Pydantic schemas
│   │   ├── services/     Google Sheets client + write-back service
│   │   └── workers/      sync worker (sheets → Postgres)
│   └── run.py
├── frontend/           Next.js 15 + Tailwind dashboard
├── docker-compose.yml  Postgres + Redis
└── .env.example        environment template
```

## Local setup

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ (LTS)
- PostgreSQL 16 + Redis 7 (via Docker Desktop, or native installs)

### 2. Configure environment
```powershell
Copy-Item .env.example .env
# edit .env: set SECRET_KEY and GOOGLE_APPLICATION_CREDENTIALS
```

**Google Sheets access (service account):**
1. Google Cloud Console → create a service account.
2. Enable the Google Sheets API.
3. Download the JSON key; set `GOOGLE_APPLICATION_CREDENTIALS` to its path.
4. Share the 3 spreadsheets with the service-account email as **Editor**.

### 3. Start infrastructure (Docker)
```powershell
docker compose up -d db redis
```

### 4. Backend
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py            # http://localhost:8000/docs
```

Bootstrap the first admin user (dev only):
```powershell
curl -X POST http://localhost:8000/api/v1/auth/setup `
  -H "Content-Type: application/json" `
  -d '{"email":"admin@example.com","password":"changeme"}'
```

### 5. Frontend
```powershell
cd frontend
npm install
npm run dev             # http://localhost:3000
```

### 6. Sync worker (separate terminal)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.workers.sync_worker
```

## API (v1, prefix `/api/v1`)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Login → access + refresh tokens |
| GET | `/auth/me` | Current user |
| GET | `/orders` | List orders (status/wilaya/channel/search/date filters, pagination) |
| GET | `/orders/{id}` | Order detail + status history |
| POST | `/orders/{id}/confirm` | Confirm order + deduct inventory |
| PATCH | `/orders/{id}/status` | Manual status change |
| GET | `/customers` / `/customers/{id}` | Customers + order history |
| GET | `/products` / `/products/{id}` | Product catalog |
| GET | `/inventory` / `/inventory/summary` | Stock levels, low-stock/out-of-stock |
| PATCH | `/inventory/{id}/stock` | Manual stock adjustment |
| GET | `/dashboard/stats` | KPIs for the overview page |

Interactive docs at `http://localhost:8000/docs`.

## Google Sheets (unchanged for n8n)

| Sheet | ID (short) | Used for |
|---|---|---|
| Products | `1PDfe5zGhGMoveWaM9gdNZmiksMeDUDnVVAFIOadDp3Q` | Catalog, price, stock, images, post ids |
| Commandes | `1_-k6B8LfGeW6ayT3-gfPT_2IJEW7kf4pqFa8tubrDA0` | Orders (append by n8n, updated by dashboard) |
| Post→product map | `1CbDGkABKJG1Jq9SuAeJHiEY7Hf_Uo_OvrKe1GwoDQ3o` | Comment → product resolution |

Sheet tabs: orders = `Commandes`; products and posts = `الورقة1` (the localized default "Sheet1"). These are set in `.env` (`SHEETS_*_TAB`) and match the n8n workflow's actual tab names.

The only planned sheet change: add a `status` column to Commandes and ensure a `stock` column exists on Products. n8n's tools preserve unknown columns, so the workflow is unaffected.

## Design guarantees

- The n8n workflow JSON is **never modified**.
- All dashboard→sheet writes are serialized through the write-back service (single worker, idempotent).
- Inventory is **fresh-read from the sheet at confirm time** to prevent overselling.
- Every table is tenant-scoped from day 1 for the future SaaS version.