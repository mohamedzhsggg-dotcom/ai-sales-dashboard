"""Legacy Google Sheets compatibility layer (temporary, removable).

Everything that knows Google Sheets lives here (plus `app/services/sheets.py`
for the low-level google client and `app/workers/sync_worker.py` for legacy
ingestion). Core business logic never imports this package.

Removal path: delete this package, `app/services/sheets.py`, the sync worker,
the `SHEETS_*` settings and the `sheet_row`/`synced_hash` columns. Nothing else
changes.
"""