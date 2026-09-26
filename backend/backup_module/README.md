# 📦 Tally Prime Backup & Restore Module

A completely isolated, self-contained microservice for creating exact, high-fidelity XML backups of Tally Prime companies and restoring them with full dependency ordering.

---

## 🌟 Key Features

- **100% Isolated:** Own SQLite database (`backup.db`), own storage directory (`backups/`), zero modifications to existing app tables or code.
- **Full Fidelity XML Backup:** Backs up all 12 key Tally Prime entity types:
  1. Groups
  2. Ledgers (with GST registrations & mailing addresses)
  3. Cost Categories
  4. Cost Centres
  5. Units of Measure
  6. Stock Groups
  7. Stock Categories
  8. Godowns / Locations
  9. Stock Items (with batch & pricing configurations)
  10. Voucher Types
  11. Vouchers (with all ledger, inventory, bill, bank, and cost center allocations)
- **Dependency-Ordered Restore:** Restores data in correct order with `ACTION="Alter"` to update existing companies cleanly.
- **Compressed ZIP Archives:** Each backup is packaged as a `.zip` archive containing individual entity XML files, `manifest.json`, and SHA-256 integrity checksums.
- **Two Deployment Modes:** Run standalone on port 8001 or mount directly into existing FastAPI apps.

---

## 🚀 Running the Service

### Option A: Standalone Server (Port 8001)

```bash
cd backend
python3 -m backup_module.main
```
Or with Uvicorn:
```bash
uvicorn backup_module.main:app --host 0.0.0.0 --port 8001 --reload
```

Interactive Swagger API docs will be available at:
`http://localhost:8001/docs`

---

### Option B: Mount in Existing FastAPI App (`app/main.py`)

Add just 2 lines to your existing `app/main.py`:
```python
from backup_module.router import backup_router

app.include_router(backup_router, prefix="/backup", tags=["Backup & Restore"])
```

Endpoints will be accessible at:
`http://localhost:8000/backup/*`

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/backup/tally/status` | Check Tally Prime XML server status and open companies |
| `GET` | `/backup/tally/companies` | List all open companies with profile details |
| `POST` | `/backup/create` | Start asynchronous company backup (`{ "company_name": "..." }`) |
| `GET` | `/backup/list` | List all backup archives with size, counts, and status |
| `GET` | `/backup/{backup_id}/status` | Check progress & details of an ongoing or completed backup |
| `GET` | `/backup/{backup_id}/download` | Download `.zip` archive |
| `DELETE` | `/backup/{backup_id}` | Delete backup archive and SQLite records |
| `POST` | `/backup/restore` | Restore backup into Tally Prime (`{ "backup_id": "...", "company_name": "..." }`) |
| `GET` | `/backup/restore/{restore_id}/status` | Check restore progress & per-entity alter/error statistics |
| `GET` | `/backup/restore/logs` | List history of restore operations |
