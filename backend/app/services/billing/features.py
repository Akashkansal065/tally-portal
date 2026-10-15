"""
features.py – Master feature registry.

Every feature key that appears in BillingPlan.feature_keys must be declared
here so the comparison table on the pricing page, the enforcement layer, and
the admin UI can all share one source of truth.

Usage:
    from app.services.billing.features import FEATURE_REGISTRY, get_feature

    feat = get_feature("einvoice_eway_bill")
    # → FeatureInfo(key="einvoice_eway_bill", label="E-Invoicing & E-Way Bill", ...)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class FeatureInfo:
    key: str
    label: str
    category: str           # groups rows in the comparison table
    info: Optional[str] = None   # tooltip / description shown in the UI


# Keep the category order stable; the pricing page renders groups in this order.
FEATURE_REGISTRY: list[FeatureInfo] = [
    # ── Data Access & Sync Engine ─────────────────────────────────────────────
    FeatureInfo("real_time_sync",       "Real-time Two-Way Tally Sync",        "Data Access & Sync Engine",
                "Continuous live sync with TallyPrime / Tally.ERP 9"),
    FeatureInfo("mobile_web_access",    "Mobile App (Android & iOS) + Web Portal", "Data Access & Sync Engine",
                "Native apps and browser portal"),
    FeatureInfo("multiple_devices",     "Simultaneous Devices per User",        "Data Access & Sync Engine"),
    FeatureInfo("multi_company_switch", "Multiple Tally Companies",             "Data Access & Sync Engine"),
    FeatureInfo("unlimited_companies",  "Unlimited Tally Companies",            "Data Access & Sync Engine"),

    # ── Sales & Ledger Management ─────────────────────────────────────────────
    FeatureInfo("outstanding_aging",         "Customer Outstandings & Ageing Buckets",    "Sales & Ledger Management"),
    FeatureInfo("pdf_whatsapp_share",        "Instant WhatsApp & PDF Invoicing Share",    "Sales & Ledger Management"),
    FeatureInfo("auto_payment_reminders",    "Automated WhatsApp Payment Reminders",      "Sales & Ledger Management",
                "Automated schedule with reminder links"),
    FeatureInfo("payment_links_collect",     "Online Payment Collection Links",           "Sales & Ledger Management",
                "Collect via UPI, Cards, Netbanking directly into bank"),
    FeatureInfo("salesman_checkin_orders",   "Salesperson GPS Check-In & Visits",         "Sales & Ledger Management",
                "Track sales reps geo-location and client visits"),
    FeatureInfo("customer_portal",           "Customer Self-Service Statement Portal",    "Sales & Ledger Management"),

    # ── Inventory & Financial Reporting ──────────────────────────────────────
    FeatureInfo("daybook_cash_bank",             "Daybook, Cash & Bank Books",              "Inventory & Financial Reporting"),
    FeatureInfo("ratio_analysis",                "Ratio Analysis & Financial Metrics",      "Inventory & Financial Reporting"),
    FeatureInfo("sales_purchase_reports",        "Item-wise Stock Valuation & Godowns",     "Inventory & Financial Reporting"),
    FeatureInfo("stock_dead_fast",               "Dead Stock, Slow Movers & Fast Movers",   "Inventory & Financial Reporting",
                "Visual insights into non-moving inventory"),
    FeatureInfo("financial_statements_drilldown","Profit & Loss, Balance Sheet Drilldown",  "Inventory & Financial Reporting"),
    FeatureInfo("bank_reconciliation",           "Bank Statement Reconciliation Auto-Match","Inventory & Financial Reporting",
                "Upload bank statement & auto-reconcile"),
    FeatureInfo("multi_godown_branch",           "Multi-Branch & Multi-Godown Analytics",   "Inventory & Financial Reporting"),

    # ── Compliance & Enterprise Controls ─────────────────────────────────────
    FeatureInfo("custom_roles_rbac",         "Role-Based Permissions (RBAC)",              "Compliance & Enterprise Controls",
                "Control ledger scope, stock group, and hide profit"),
    FeatureInfo("einvoice_eway_bill",         "Govt E-Invoicing (IRN & QR) + E-Way Bill",  "Compliance & Enterprise Controls",
                "Generate certified IRN & QR without visiting the portal"),
    FeatureInfo("audit_trail_deleted_logs",   "Audit Trail & Deleted Records History",     "Compliance & Enterprise Controls",
                "Track what was edited or deleted in Tally"),
    FeatureInfo("approval_rules_matrix",      "Custom Voucher Approval Matrix",            "Compliance & Enterprise Controls"),
    FeatureInfo("dedicated_account_manager",  "Dedicated VIP Support Manager",             "Compliance & Enterprise Controls"),
    FeatureInfo("custom_onboarding_vip",      "Custom Onboarding & VIP Support",           "Compliance & Enterprise Controls"),
    FeatureInfo("priority_sync_support",      "Fast Sync Engine & Priority Support",       "Compliance & Enterprise Controls"),
]

_REGISTRY_MAP: dict[str, FeatureInfo] = {f.key: f for f in FEATURE_REGISTRY}


def get_feature(key: str) -> Optional[FeatureInfo]:
    """Return the FeatureInfo for *key*, or None if it is not registered."""
    return _REGISTRY_MAP.get(key)
