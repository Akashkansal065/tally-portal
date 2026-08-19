import asyncio
import os
import sys
import json
import time
import traceback
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timezone
from decimal import Decimal

import httpx
from sqlalchemy.future import select
from sqlalchemy import text

# Ensure backend root is in sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.main import app
from app.core.database import AsyncSessionLocal, engine
from app.models.portal_core import User, Company, Role, SyncQueue, DeletedRecordAudit, SyncTrafficLog
from app.models.tally_core import (
    MstVoucherType, MstLedger, MstGroup, MstUom, MstStockGroup, 
    MstStockCategory, MstGodown, MstStockItem, Batch, TrnVoucher,
    TrnAccounting, TrnInventory, TrnBill, BillAllocation, CostCenter
)
from app.core.security import create_access_token


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"


class E2ETraceRecorder:
    """Records and formats test steps, request payloads, responses, latency, and assertions."""
    def __init__(self, suite_name: str):
        self.suite_name = suite_name
        self.steps: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.passed_count = 0
        self.failed_count = 0

    def log_step(
        self,
        name: str,
        method: str,
        endpoint: str,
        request_data: Any,
        status_code: int,
        response_data: Any,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
        assertions: Optional[List[str]] = None
    ):
        step_record = {
            "step": len(self.steps) + 1,
            "name": name,
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
            "success": success,
            "assertions": assertions or [],
            "error": error,
            "request_payload": request_data,
            "response_payload": response_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        self.steps.append(step_record)
        if success:
            self.passed_count += 1
            print(f"  {Colors.BOLD}{Colors.GREEN}[PASS]{Colors.RESET} {Colors.WHITE}{name}{Colors.RESET} ({Colors.CYAN}{method} {endpoint}{Colors.RESET}) -> {Colors.GREEN}{status_code}{Colors.RESET} [{step_record['duration_ms']}ms]")
        else:
            self.failed_count += 1
            print(f"  {Colors.BOLD}{Colors.RED}[FAIL]{Colors.RESET} {Colors.BOLD}{name}{Colors.RESET} ({method} {endpoint}) -> {Colors.RED}{status_code}{Colors.RESET} [{step_record['duration_ms']}ms]")
            if error:
                print(f"         {Colors.RED}✖ Error: {error}{Colors.RESET}")
            if response_data:
                print(f"         {Colors.YELLOW}↳ Response: {json.dumps(response_data, default=str)[:300]}{Colors.RESET}")

    def summary(self) -> Dict[str, Any]:
        total_time = round((time.time() - self.start_time) * 1000, 2)
        return {
            "suite": self.suite_name,
            "total_steps": len(self.steps),
            "passed": self.passed_count,
            "failed": self.failed_count,
            "total_duration_ms": total_time,
            "steps": self.steps
        }


class E2EClient:
    """Authenticated Async HTTP Client with rich tracing and helper assertions."""
    def __init__(self, recorder: E2ETraceRecorder):
        self.recorder = recorder
        self.token: Optional[str] = None
        self.user: Optional[User] = None
        self.company: Optional[Company] = None
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        # Using ASGITransport for fast, robust in-process execution with real DB
        transport = httpx.ASGITransport(app=app)
        self._client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def authenticate(self):
        """Initializes user session & generates bearer token."""
        import hashlib
        from datetime import timedelta
        from app.models.portal_core import UserSession
        async with AsyncSessionLocal() as session:
            # Find or get first admin user
            res = await session.execute(select(User).where(User.is_active == True).limit(1))
            self.user = res.scalars().first()
            if not self.user:
                raise RuntimeError("No active user found in database. Seed global data first.")
            
            comp_res = await session.execute(select(Company).where(Company.company_id == self.user.company_id))
            self.company = comp_res.scalars().first()
            
            # Generate valid bearer token
            self.token = create_access_token(subject=self.user.user_id)
            token_hash = hashlib.sha256(self.token.encode()).hexdigest()
            session_rec = UserSession(
                user_id=self.user.user_id,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7)
            )
            session.add(session_rec)
            await session.commit()

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        step_name: str,
        json_data: Any = None,
        params: Any = None,
        expected_status: int = 200,
        assertion_desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Performs request, measures latency, checks status, and logs into trace recorder."""
        t0 = time.time()
        assertions = [assertion_desc] if assertion_desc else []
        try:
            resp = await self._client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params,
                headers=self.headers,
                timeout=30.0
            )
            duration_ms = (time.time() - t0) * 1000
            
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text}

            success = (resp.status_code == expected_status)
            err_msg = None
            if not success:
                err_msg = f"Expected status {expected_status}, received {resp.status_code}. Response: {body}"

            self.recorder.log_step(
                name=step_name,
                method=method,
                endpoint=endpoint,
                request_data=json_data or params,
                status_code=resp.status_code,
                response_data=body,
                duration_ms=duration_ms,
                success=success,
                error=err_msg,
                assertions=assertions
            )
            
            if not success:
                raise AssertionError(f"Step '{step_name}' failed: {err_msg}")
                
            return body
        except Exception as e:
            if not isinstance(e, AssertionError):
                duration_ms = (time.time() - t0) * 1000
                self.recorder.log_step(
                    name=step_name,
                    method=method,
                    endpoint=endpoint,
                    request_data=json_data or params,
                    status_code=500,
                    response_data={"exception": str(e), "traceback": traceback.format_exc()},
                    duration_ms=duration_ms,
                    success=False,
                    error=str(e),
                    assertions=assertions
                )
            raise


class MasterDataManager:
    """Manages prerequisite test entities (UOM, Godowns, Items, Ledgers, Cost Centers)."""
    def __init__(self, client: E2EClient):
        self.client = client
        self.created_masters: Dict[str, List[int]] = {
            "vouchers": [],
            "stock_items": [],
            "godowns": [],
            "uoms": [],
            "stock_groups": [],
            "stock_categories": [],
            "batches": [],
            "ledgers": [],
            "cost_centers": [],
            "voucher_types": []
        }
        self.voucher_types_map: Dict[str, int] = {}
        self.data: Dict[str, Any] = {}

    async def clean_stale_e2e_records(self):
        """Cleans up any leftover E2E records from previously failed/interrupted runs."""
        async with AsyncSessionLocal() as session:
            from app.core.config import settings
            t_schema = settings.TALLY_DATABASE_NAME
            try:
                await session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                # 1. Delete E2E vouchers & child records
                await session.execute(text(f"DELETE FROM {t_schema}.voucher_accounting_allocations WHERE stock_entry_id IN (SELECT stock_entry_id FROM {t_schema}.inventory_entries WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%'))"))
                await session.execute(text(f"DELETE FROM {t_schema}.bank_allocations WHERE entry_id IN (SELECT entry_id FROM {t_schema}.voucher_entries WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%'))"))
                await session.execute(text(f"DELETE FROM {t_schema}.bill_allocations WHERE voucher_entry_id IN (SELECT entry_id FROM {t_schema}.voucher_entries WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%'))"))
                await session.execute(text(f"DELETE FROM {t_schema}.voucher_entries WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.inventory_entries WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.bills WHERE voucher_id IN (SELECT voucher_id FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.vouchers WHERE reference_number LIKE 'E2E%' OR narration LIKE '%E2E%'"))

                # 2. Delete E2E stock items & child records
                await session.execute(text(f"DELETE FROM {t_schema}.stock_item_opening_balance WHERE stock_item_id IN (SELECT stock_item_id FROM {t_schema}.stock_items WHERE name LIKE 'E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.stock_item_gst_details WHERE stock_item_id IN (SELECT stock_item_id FROM {t_schema}.stock_items WHERE name LIKE 'E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.stock_item_mrp_details WHERE stock_item_id IN (SELECT stock_item_id FROM {t_schema}.stock_items WHERE name LIKE 'E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.stock_item_tariff_details WHERE stock_item_id IN (SELECT stock_item_id FROM {t_schema}.stock_items WHERE name LIKE 'E2E%')"))
                await session.execute(text(f"DELETE FROM {t_schema}.stock_items WHERE name LIKE 'E2E%'"))

                # 3. Delete E2E godowns
                await session.execute(text(f"DELETE FROM {t_schema}.godowns WHERE name LIKE 'E2E%'"))
                # 4. Delete E2E stock groups
                await session.execute(text(f"DELETE FROM {t_schema}.stock_groups WHERE name LIKE 'E2E%'"))
                # 5. Delete E2E UOMs
                await session.execute(text(f"DELETE FROM {t_schema}.units_of_measure WHERE symbol LIKE 'E2E%' OR name LIKE 'E2E%'"))
                # 6. Delete E2E Ledgers
                await session.execute(text(f"DELETE FROM {t_schema}.ledgers WHERE name LIKE 'E2E%'"))
                # 7. Delete E2E Cost Centres & Categories
                await session.execute(text(f"DELETE FROM {t_schema}.cost_centres WHERE name LIKE 'E2E%'"))
                await session.execute(text(f"DELETE FROM {t_schema}.cost_categories WHERE name LIKE 'E2E%'"))

                await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                await session.commit()
            except Exception:
                await session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                await session.commit()

    async def initialize_and_seed_masters(self):
        """Creates or loads all required master data via REST APIs."""
        print("  [*] Purging any leftover stale E2E test records...")
        await self.clean_stale_e2e_records()

        print("  [*] Fetching voucher types...")
        vt_list = await self.client.request(
            "GET", "/vouchers/types",
            step_name="Fetch Voucher Types",
            expected_status=200
        )
        for vt in vt_list:
            name = vt.get("name")
            parent = vt.get("parent_type") or name
            vt_id = vt.get("voucher_type_id")
            self.voucher_types_map[name] = vt_id
            if parent not in self.voucher_types_map:
                self.voucher_types_map[parent] = vt_id

        # 1. Simple UOM
        print("  [*] Creating/Verifying UOM...")
        uoms = await self.client.request("GET", "/inventory/uoms", step_name="List Existing UOMs")
        existing_nos = next((u for u in uoms if u.get("symbol", "").lower() == "nos"), None)
        if existing_nos:
            self.data["uom_nos_id"] = existing_nos["unit_id"]
        else:
            uom_resp = await self.client.request(
                "POST", "/inventory/uoms",
                step_name="Create Test UOM (nos)",
                json_data={
                    "name": "nos",
                    "symbol": "nos",
                    "original_name": "Numbers",
                    "is_simple_unit": True,
                    "decimal_places": 0
                },
                expected_status=200
            )
            self.data["uom_nos_id"] = uom_resp["unit_id"]
            self.created_masters["uoms"].append(uom_resp["unit_id"])

        # 2. Stock Group
        print("  [*] Creating/Verifying Stock Group...")
        groups_list = await self.client.request("GET", "/inventory/groups", step_name="List Existing Stock Groups")
        existing_grp = next((g for g in groups_list if g.get("name") == "E2E Electronics"), None)
        if existing_grp:
            self.data["stock_group_id"] = existing_grp["stock_group_id"]
        else:
            grp_resp = await self.client.request(
                "POST", "/inventory/groups",
                step_name="Create Test Stock Group",
                json_data={
                    "name": "E2E Electronics",
                    "is_active": True
                },
                expected_status=200
            )
            self.data["stock_group_id"] = grp_resp["stock_group_id"]
            self.created_masters["stock_groups"].append(grp_resp["stock_group_id"])

        # 3. Godowns (Source & Destination)
        print("  [*] Creating/Verifying Test Godowns...")
        godowns_list = await self.client.request("GET", "/inventory/godowns", step_name="List Existing Godowns")
        g1_exist = next((g for g in godowns_list if g.get("name") == "E2E Central Godown - Bangalore"), None)
        if g1_exist:
            self.data["godown_blr_id"] = g1_exist["godown_id"]
        else:
            g1 = await self.client.request(
                "POST", "/inventory/godowns",
                step_name="Create Central Godown",
                json_data={"name": "E2E Central Godown - Bangalore", "address": "Indiranagar, Bangalore"},
                expected_status=200
            )
            self.data["godown_blr_id"] = g1["godown_id"]
            self.created_masters["godowns"].append(g1["godown_id"])

        g2_exist = next((g for g in godowns_list if g.get("name") == "E2E Secondary Godown - Delhi"), None)
        if g2_exist:
            self.data["godown_delhi_id"] = g2_exist["godown_id"]
        else:
            g2 = await self.client.request(
                "POST", "/inventory/godowns",
                step_name="Create Secondary Godown",
                json_data={"name": "E2E Secondary Godown - Delhi", "address": "Connaught Place, Delhi"},
                expected_status=200
            )
            self.data["godown_delhi_id"] = g2["godown_id"]
            self.created_masters["godowns"].append(g2["godown_id"])

        # 4. Stock Item with Opening Stock 100 NOS @ 25,000.00
        print("  [*] Creating/Verifying Test Stock Item...")
        items_list = await self.client.request("GET", "/inventory/items", step_name="List Existing Stock Items")
        item_exist = next((i for i in items_list if i.get("name") == "E2E Test 4K OLED Monitor 32inch"), None)
        if item_exist:
            self.data["stock_item_id"] = item_exist["stock_item_id"]
        else:
            item_resp = await self.client.request(
                "POST", "/inventory/items",
                step_name="Create Test Stock Item",
                json_data={
                    "name": "E2E Test 4K OLED Monitor 32inch",
                    "stock_group_id": self.data["stock_group_id"],
                    "unit_id": self.data["uom_nos_id"],
                    "opening_qty": 100.0,
                    "opening_rate": 25000.0,
                    "gst_rate_percent": 18.0,
                    "hsn_code": "85285200"
                },
                expected_status=200
            )
            self.data["stock_item_id"] = item_resp["stock_item_id"]
            self.created_masters["stock_items"].append(item_resp["stock_item_id"])

        # 5. Ledgers Setup
        print("  [*] Fetching Account Groups & Existing Ledgers...")
        acct_groups = await self.client.request("GET", "/ledgers/groups", step_name="Fetch Account Groups")
        group_by_name = {g["name"]: g["group_id"] for g in acct_groups}
        
        all_ledgers = await self.client.request("GET", "/ledgers", step_name="Fetch Existing Ledgers")
        ledger_by_name = {l["name"]: l["ledger_id"] for l in all_ledgers}

        debtors_grp = group_by_name.get("Sundry Debtors", 1)
        creditors_grp = group_by_name.get("Sundry Creditors", 2)
        sales_grp = group_by_name.get("Sales Accounts", 3)
        purch_grp = group_by_name.get("Purchase Accounts", 4)
        bank_grp = group_by_name.get("Bank Accounts", 5)
        cash_grp = group_by_name.get("Cash-in-hand", 6)
        duties_grp = group_by_name.get("Duties & Taxes", 7)
        exp_grp = group_by_name.get("Direct Expenses") or group_by_name.get("Indirect Expenses", 8)

        async def get_or_create_ledger(name: str, payload: dict, step_name: str) -> int:
            if name in ledger_by_name:
                return ledger_by_name[name]
            resp = await self.client.request("POST", "/ledgers", step_name=step_name, json_data=payload, expected_status=200)
            lid = resp["ledger_id"]
            self.created_masters["ledgers"].append(lid)
            ledger_by_name[name] = lid
            return lid

        # 5a. Sundry Debtor
        self.data["debtor_ledger_id"] = await get_or_create_ledger(
            "E2E Alpha Retailers Corp",
            {
                "name": "E2E Alpha Retailers Corp",
                "group_id": debtors_grp,
                "credit_period_days": 30,
                "credit_limit": 5000000.0,
                "bill_by_bill": True,
                "state": "Karnataka"
            },
            "Create Debtor (Alpha Retailers)"
        )

        # 5b. Sundry Creditor
        self.data["creditor_ledger_id"] = await get_or_create_ledger(
            "E2E Zenith Global Supplies Ltd",
            {
                "name": "E2E Zenith Global Supplies Ltd",
                "group_id": creditors_grp,
                "credit_period_days": 45,
                "bill_by_bill": True,
                "state": "Karnataka"
            },
            "Create Creditor (Zenith Supplies)"
        )

        # 5c. Sales Ledger
        self.data["sales_ledger_id"] = await get_or_create_ledger(
            "E2E Domestic Sales 18%",
            {
                "name": "E2E Domestic Sales 18%",
                "group_id": sales_grp,
                "is_active": True
            },
            "Create Sales Ledger"
        )

        # 5d. Purchase Ledger
        self.data["purchase_ledger_id"] = await get_or_create_ledger(
            "E2E Domestic Purchase 18%",
            {
                "name": "E2E Domestic Purchase 18%",
                "group_id": purch_grp,
                "is_active": True
            },
            "Create Purchase Ledger"
        )

        # 5e. Bank Ledger
        self.data["bank_ledger_id"] = await get_or_create_ledger(
            "E2E HDFC Bank Current A/c",
            {
                "name": "E2E HDFC Bank Current A/c",
                "group_id": bank_grp,
                "account_number": "50200012345678",
                "ifsc_code": "HDFC0001234"
            },
            "Create HDFC Bank Ledger"
        )

        # 5f. Cash Ledger
        self.data["cash_ledger_id"] = await get_or_create_ledger(
            "E2E Petty Cash in Hand",
            {
                "name": "E2E Petty Cash in Hand",
                "group_id": cash_grp
            },
            "Create Cash Ledger"
        )

        # 5g. Taxes (CGST & SGST)
        self.data["cgst_ledger_id"] = await get_or_create_ledger(
            "E2E CGST @ 9%",
            {"name": "E2E CGST @ 9%", "group_id": duties_grp},
            "Create CGST 9% Ledger"
        )

        self.data["sgst_ledger_id"] = await get_or_create_ledger(
            "E2E SGST @ 9%",
            {"name": "E2E SGST @ 9%", "group_id": duties_grp},
            "Create SGST 9% Ledger"
        )

        # 5h. Expense Ledger
        self.data["expense_ledger_id"] = await get_or_create_ledger(
            "E2E Corporate Office Rent",
            {"name": "E2E Corporate Office Rent", "group_id": exp_grp},
            "Create Rent Expense Ledger"
        )

        # 6. Cost Category & Cost Centre
        cats = await self.client.request("GET", "/masters/cost-categories", step_name="Fetch Existing Cost Categories")
        existing_cat = next((c for c in cats if c.get("name") == "E2E Primary Cost Category"), None)
        if existing_cat:
            self.data["cost_category_id"] = existing_cat["category_id"]
        else:
            cat_resp = await self.client.request(
                "POST", "/masters/cost-categories",
                step_name="Create Cost Category",
                json_data={"name": "E2E Primary Cost Category", "allocate_revenue": True},
                expected_status=200
            )
            self.data["cost_category_id"] = cat_resp["category_id"]
            self.created_masters.setdefault("cost_categories", []).append(cat_resp["category_id"])

        ccs = await self.client.request("GET", "/masters/cost-centres", step_name="Fetch Existing Cost Centres")
        existing_cc = next((c for c in ccs if c.get("name") == "E2E Bangalore Sales HQ"), None)
        if existing_cc:
            self.data["cost_center_id"] = existing_cc["cost_centre_id"]
        else:
            cc_resp = await self.client.request(
                "POST", "/masters/cost-centres",
                step_name="Create Cost Centre",
                json_data={
                    "name": "E2E Bangalore Sales HQ",
                    "category_id": self.data["cost_category_id"]
                },
                expected_status=201
            )
            self.data["cost_center_id"] = cc_resp["cost_centre_id"]
            self.created_masters.setdefault("cost_centers", []).append(cc_resp["cost_centre_id"])

        print("  [SUCCESS] All prerequisite master data created successfully.")

    async def get_stock_item_closing_qty(self, stock_item_id: int) -> float:
        """Retrieves live closing stock quantity from backend API."""
        item = await self.client.request(
            "GET", f"/inventory/items/{stock_item_id}",
            step_name="Query Stock Item Closing Qty"
        )
        val = item.get("closing_balance")
        if val is None:
            val = item.get("closing_qty")
        if val is None:
            val = item.get("opening_qty")
        return float(val or 0.0)

    async def teardown_all(self):
        """Cleans up created vouchers and test masters in proper dependency order."""
        print("\n  [CLEANUP] Starting master teardown...")
        # 1. Delete all tracked vouchers
        for v_id in reversed(self.created_masters["vouchers"]):
            try:
                await self.client.request(
                    "DELETE", f"/vouchers/{v_id}",
                    step_name=f"Teardown Voucher #{v_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete voucher {v_id}: {e}")

        # 2. Delete Stock Items
        for item_id in self.created_masters["stock_items"]:
            try:
                await self.client.request(
                    "DELETE", f"/inventory/items/{item_id}",
                    step_name=f"Teardown Stock Item #{item_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete stock item {item_id}: {e}")

        # 3. Delete Godowns
        for g_id in self.created_masters["godowns"]:
            try:
                await self.client.request(
                    "DELETE", f"/inventory/godowns/{g_id}",
                    step_name=f"Teardown Godown #{g_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete godown {g_id}: {e}")

        # 4. Delete Stock Groups
        for grp_id in self.created_masters["stock_groups"]:
            try:
                await self.client.request(
                    "DELETE", f"/inventory/groups/{grp_id}",
                    step_name=f"Teardown Stock Group #{grp_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete stock group {grp_id}: {e}")

        # 5. Delete UOMs
        for u_id in self.created_masters["uoms"]:
            try:
                await self.client.request(
                    "DELETE", f"/inventory/uoms/{u_id}",
                    step_name=f"Teardown UOM #{u_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete UOM {u_id}: {e}")

        # 6. Delete Ledgers
        for l_id in self.created_masters["ledgers"]:
            try:
                await self.client.request(
                    "DELETE", f"/ledgers/{l_id}",
                    step_name=f"Teardown Ledger #{l_id}",
                    expected_status=200
                )
            except Exception as e:
                print(f"    [WARN] Could not delete ledger {l_id}: {e}")

        # 7. Delete Cost Centres
        for cc_id in self.created_masters.get("cost_centers", []):
            try:
                await self.client.request(
                    "DELETE", f"/masters/cost-centres/{cc_id}",
                    step_name=f"Teardown Cost Centre #{cc_id}",
                    expected_status=204
                )
            except Exception as e:
                print(f"    [WARN] Could not delete cost centre {cc_id}: {e}")

        # 8. Delete Cost Categories
        for cat_id in self.created_masters.get("cost_categories", []):
            try:
                await self.client.request(
                    "DELETE", f"/masters/cost-categories/{cat_id}",
                    step_name=f"Teardown Cost Category #{cat_id}",
                    expected_status=204
                )
            except Exception as e:
                print(f"    [WARN] Could not delete cost category {cat_id}: {e}")

        print("  [SUCCESS] Teardown completed successfully.\n")
