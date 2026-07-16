-- ============================================================
-- Open Tally-Clone : Schema Extension — GST Returns (GSTR-1 / GSTR-3B)
-- Depends on: schema.sql, schema_orders_payments.sql (bills), tax_rates
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. RETURN PERIODS (one row per company per return type per month)
-- ------------------------------------------------------------
CREATE TABLE gst_return_periods (
    return_period_id    BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    return_type         ENUM('GSTR1','GSTR3B') NOT NULL,
    period_month        TINYINT NOT NULL,
    period_year         SMALLINT NOT NULL,
    status              ENUM('Draft','Filed') DEFAULT 'Draft',
    filed_date          DATE NULL,
    arn                 VARCHAR(30) NULL,            -- Acknowledgement Reference Number from GST portal after filing
    filed_by            INT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (filed_by) REFERENCES users(user_id),
    UNIQUE KEY uq_return_period (company_id, return_type, period_month, period_year)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. GSTR-1 (Outward Supplies) — line-level detail, built from vouchers
-- ------------------------------------------------------------
-- Rather than re-deriving figures from `vouchers` every time a filed
-- return is viewed (risky — ledger data can be edited later), GSTR-1
-- line items are SNAPSHOTTED into this table at generation time. Once
-- return_period.status = 'Filed', these rows become immutable (enforced
-- in the app layer, not by MySQL).
CREATE TABLE gstr1_line_items (
    line_item_id         BIGINT AUTO_INCREMENT PRIMARY KEY,
    return_period_id     BIGINT NOT NULL,
    voucher_id           BIGINT NOT NULL,             -- source Sales voucher
    supply_type          ENUM('B2B','B2CL','B2CS','Export','Nil Rated','Exempt') NOT NULL,
    party_gstin          VARCHAR(15),                  -- NULL for B2C
    invoice_number       VARCHAR(30) NOT NULL,
    invoice_date         DATE NOT NULL,
    place_of_supply      VARCHAR(50) NOT NULL,         -- state code, determines CGST+SGST vs IGST
    taxable_value        DECIMAL(18,2) NOT NULL,
    cgst_amount          DECIMAL(18,2) DEFAULT 0,
    sgst_amount          DECIMAL(18,2) DEFAULT 0,
    igst_amount          DECIMAL(18,2) DEFAULT 0,
    cess_amount          DECIMAL(18,2) DEFAULT 0,
    invoice_value        DECIMAL(18,2) NOT NULL,
    FOREIGN KEY (return_period_id) REFERENCES gst_return_periods(return_period_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id)
) ENGINE=InnoDB;

-- HSN-wise summary (a required GSTR-1 table — "HSN Summary")
CREATE TABLE gstr1_hsn_summary (
    hsn_summary_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    return_period_id     BIGINT NOT NULL,
    hsn_code             VARCHAR(10) NOT NULL,
    description          VARCHAR(150),
    uqc                  VARCHAR(20),                  -- Unit Quantity Code
    total_quantity       DECIMAL(14,3) NOT NULL,
    taxable_value        DECIMAL(18,2) NOT NULL,
    cgst_amount          DECIMAL(18,2) DEFAULT 0,
    sgst_amount          DECIMAL(18,2) DEFAULT 0,
    igst_amount          DECIMAL(18,2) DEFAULT 0,
    cess_amount          DECIMAL(18,2) DEFAULT 0,
    FOREIGN KEY (return_period_id) REFERENCES gst_return_periods(return_period_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. GSTR-3B (Summary Return — outward tax liability + ITC + net payable)
-- ------------------------------------------------------------
CREATE TABLE gstr3b_summary (
    summary_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    return_period_id     BIGINT NOT NULL UNIQUE,

    -- 3.1 Outward supplies
    outward_taxable_value DECIMAL(18,2) DEFAULT 0,
    outward_cgst          DECIMAL(18,2) DEFAULT 0,
    outward_sgst          DECIMAL(18,2) DEFAULT 0,
    outward_igst          DECIMAL(18,2) DEFAULT 0,
    outward_cess          DECIMAL(18,2) DEFAULT 0,

    -- 4. Eligible ITC (Input Tax Credit)
    itc_igst_available    DECIMAL(18,2) DEFAULT 0,
    itc_cgst_available    DECIMAL(18,2) DEFAULT 0,
    itc_sgst_available    DECIMAL(18,2) DEFAULT 0,
    itc_cess_available    DECIMAL(18,2) DEFAULT 0,
    itc_reversed          DECIMAL(18,2) DEFAULT 0,     -- ITC reversed for ineligible purchases

    -- Net payable after ITC set-off
    net_igst_payable      DECIMAL(18,2) DEFAULT 0,
    net_cgst_payable      DECIMAL(18,2) DEFAULT 0,
    net_sgst_payable      DECIMAL(18,2) DEFAULT 0,
    net_cess_payable      DECIMAL(18,2) DEFAULT 0,

    -- Payment
    tax_paid_via_cash     DECIMAL(18,2) DEFAULT 0,
    tax_paid_via_itc      DECIMAL(18,2) DEFAULT 0,
    interest_paid         DECIMAL(18,2) DEFAULT 0,
    late_fee_paid         DECIMAL(18,2) DEFAULT 0,

    FOREIGN KEY (return_period_id) REFERENCES gst_return_periods(return_period_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. INPUT TAX CREDIT (ITC) LEDGER — tracks ITC from Purchase vouchers
--    that feeds into gstr3b_summary.itc_*_available
-- ------------------------------------------------------------
CREATE TABLE itc_entries (
    itc_entry_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id            INT NOT NULL,
    voucher_id            BIGINT NOT NULL,             -- source Purchase voucher
    supplier_gstin        VARCHAR(15),
    invoice_number        VARCHAR(30) NOT NULL,
    invoice_date          DATE NOT NULL,
    taxable_value         DECIMAL(18,2) NOT NULL,
    cgst_amount           DECIMAL(18,2) DEFAULT 0,
    sgst_amount           DECIMAL(18,2) DEFAULT 0,
    igst_amount           DECIMAL(18,2) DEFAULT 0,
    cess_amount           DECIMAL(18,2) DEFAULT 0,
    eligibility           ENUM('Eligible','Ineligible','Partially Eligible') DEFAULT 'Eligible',
    claimed_return_period_id BIGINT NULL,               -- which GSTR-3B period this ITC was claimed in
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id),
    FOREIGN KEY (claimed_return_period_id) REFERENCES gst_return_periods(return_period_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_gstr1_lines_period ON gstr1_line_items (return_period_id, supply_type);
CREATE INDEX idx_itc_entries_period ON itc_entries (claimed_return_period_id);
CREATE INDEX idx_itc_entries_company ON itc_entries (company_id, invoice_date);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application flow notes:
-- 1. "Generate GSTR-1 for [month]" -> app creates gst_return_periods row
--    (status=Draft) -> queries all Sales vouchers in that month, classifies
--    each by supply_type (B2B if party has GSTIN, B2CL/B2CS by invoice
--    value threshold, etc.) -> snapshots into gstr1_line_items and
--    gstr1_hsn_summary.
-- 2. Admin reviews the draft in the admin panel, can regenerate as many
--    times as needed while status = 'Draft'.
-- 3. On "Mark as Filed" (after actually filing on the government GST
--    portal): user enters the ARN -> status flips to 'Filed' -> rows in
--    gstr1_line_items/gstr1_hsn_summary become read-only.
-- 4. GSTR-3B: outward figures come from GSTR-1 data for the same period;
--    ITC figures come from itc_entries where claimed_return_period_id
--    matches. Net payable = outward tax − eligible ITC (per tax head,
--    IGST/CGST/SGST cannot be cross-utilized freely — this set-off logic
--    lives in the FastAPI report_service, following GST set-off rules).
-- ------------------------------------------------------------
