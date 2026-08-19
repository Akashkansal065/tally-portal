# Tally Sync Validation Guide

This document describes how to validate the **Tally Bidirectional Sync Engine** implementation step-by-step.

---

## Prerequisites

Ensure that the MySQL Docker container is running:
```bash
docker ps | grep mytally-mysql
```

---

## Step 1: Reset & Apply Migrations

To ensure clean database schemas (without cross-tenant unique constraint collisions on Tally GUIDs), reset the database and run the migrations:

```bash
# 1. Drop and recreate the database
docker exec -i mytally-mysql mysql -u root -prootpassword -e "DROP DATABASE IF EXISTS mytally_db; CREATE DATABASE mytally_db;"

# 2. Run the Python-based migrations (from backend folder)
./venv/bin/alembic upgrade head

# 3. Seed default roles, modules, and permissions
python3 app/core/seed.py
```

---

## Step 2: Start the FastAPI Server

Launch the development server to start listening for inbound and outbound sync operations:

```bash
# From backend folder
./venv/bin/python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

## Step 3: Run the Auto-Validation Suite

Execute the dedicated integration test script to validate all components 1-by-1:

```bash
# Runs registration, login, inbound XML sign parsing, outbound XML generation, and queue acknowledgments
python3 scratch/test_tally_sync.py
```

*Note: For regression testing, the script is also stored inside the Gemini artifacts directory at `/Users/akashkansal/.gemini/antigravity-ide/brain/10450464-09b8-4e21-bd1a-8fe898a360ff/scratch/test_tally_sync.py`.*

---

## Step 4: Run the Local Sync Bridge Daemon

To test polling changes back-and-forth between a local Tally Prime XML server running on `http://localhost:9000` and the Web ERP:

```bash
python3 scratch/tally_sync_daemon.py
```
