-- ============================================================
-- Open Tally-Clone : Core MySQL Schema (Phase 1 + Phase 2 base)
-- Engine: MySQL 8.0+
-- Charset: utf8mb4 (for ₹ symbol, multi-language ledger names)
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. COMPANY & FINANCIAL YEAR  (Tally supports multi-company)
-- ------------------------------------------------------------
CREATE TABLE companies (
    company_id          INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(150) NOT NULL,
    gstin               VARCHAR(15),
    pan                 VARCHAR(10),
    address_line1       VARCHAR(200),
    address_line2       VARCHAR(200),
    city                VARCHAR(100),
    state               VARCHAR(100),
    pincode             VARCHAR(10),
    country             VARCHAR(100) DEFAULT 'India',
    base_currency       VARCHAR(10) DEFAULT 'INR',
    books_begin_date    DATE NOT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE financial_years (
    fy_id               INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    is_locked           BOOLEAN DEFAULT FALSE,   -- prevents backdated entries once books are closed
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    UNIQUE KEY uq_fy (company_id, start_date, end_date)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. USERS, ROLES & PERMISSIONS (multi-user, role-based access)
-- ------------------------------------------------------------
CREATE TABLE roles (
    role_id             INT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(50) NOT NULL UNIQUE,   -- Admin, Accountant, Auditor, DataEntry, Viewer
    description         VARCHAR(200)
) ENGINE=InnoDB;

CREATE TABLE users (
    user_id             INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    username            VARCHAR(50) NOT NULL,
    email               VARCHAR(120) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    role_id             INT NOT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    last_login          TIMESTAMP NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(role_id),
    UNIQUE KEY uq_user_email (company_id, email)
) ENGINE=InnoDB;

-- Fine-grained permissions per role (e.g. can_post_voucher, can_view_reports, can_delete)
CREATE TABLE permissions (
    permission_id       INT AUTO_INCREMENT PRIMARY KEY,
    role_id             INT NOT NULL,
    module              VARCHAR(50) NOT NULL,   -- 'vouchers','ledgers','inventory','reports','users'
    can_create          BOOLEAN DEFAULT FALSE,
    can_read            BOOLEAN DEFAULT TRUE,
    can_update          BOOLEAN DEFAULT FALSE,
    can_delete          BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. CHART OF ACCOUNTS (Tally's Groups + Ledgers hierarchy)
-- ------------------------------------------------------------
-- Tally has ~28 primary groups (Capital Account, Loans, Fixed Assets,
-- Current Assets, Current Liabilities, Sales, Purchase, Direct/Indirect
-- Expenses & Income, etc). We model it as a self-referencing tree so
-- users can create custom sub-groups too.
CREATE TABLE account_groups (
    group_id            INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(100) NOT NULL,
    parent_group_id     INT NULL,
    nature              ENUM('Asset','Liability','Income','Expense') NOT NULL,
    affects_gross_profit BOOLEAN DEFAULT FALSE,   -- for P&L classification (direct vs indirect)
    is_system_defined   BOOLEAN DEFAULT FALSE,    -- seed groups vs user-created
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_group_id) REFERENCES account_groups(group_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE ledgers (
    ledger_id           INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(150) NOT NULL,
    group_id            INT NOT NULL,
    opening_balance     DECIMAL(18,2) DEFAULT 0.00,
    opening_balance_type ENUM('Dr','Cr') DEFAULT 'Dr',
    gstin               VARCHAR(15),               -- for party ledgers (customer/vendor)
    address             VARCHAR(300),
    state               VARCHAR(100),
    is_bank_account     BOOLEAN DEFAULT FALSE,
    bank_account_no     VARCHAR(30),
    bank_ifsc           VARCHAR(15),
    credit_limit        DECIMAL(18,2) DEFAULT NULL,
    credit_period_days  INT DEFAULT NULL,
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES account_groups(group_id),
    UNIQUE KEY uq_ledger_name (company_id, name)
) ENGINE=InnoDB;

-- Cost centers (departments/projects for cost-center-wise P&L)
CREATE TABLE cost_centers (
    cost_center_id      INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(100) NOT NULL,
    parent_id           INT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES cost_centers(cost_center_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. VOUCHER TYPES & VOUCHERS (the heart of double-entry)
-- ------------------------------------------------------------
CREATE TABLE voucher_types (
    voucher_type_id     INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(50) NOT NULL,     -- Payment, Receipt, Journal, Sales, Purchase, Contra, Debit Note, Credit Note
    abbreviation        VARCHAR(10),
    numbering_method    ENUM('Automatic','Manual') DEFAULT 'Automatic',
    prefix              VARCHAR(10) DEFAULT '',
    next_number         INT DEFAULT 1,
    is_system_defined   BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE vouchers (
    voucher_id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    voucher_type_id     INT NOT NULL,
    voucher_number       VARCHAR(30) NOT NULL,
    voucher_date        DATE NOT NULL,
    reference_number    VARCHAR(50),
    narration           TEXT,
    total_amount        DECIMAL(18,2) NOT NULL DEFAULT 0.00,
    is_cancelled        BOOLEAN DEFAULT FALSE,
    is_optional         BOOLEAN DEFAULT FALSE,     -- Tally's "optional voucher" (not posted to ledgers)
    created_by          INT NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_type_id) REFERENCES voucher_types(voucher_type_id),
    FOREIGN KEY (created_by) REFERENCES users(user_id),
    UNIQUE KEY uq_voucher_number (company_id, voucher_type_id, voucher_number)
) ENGINE=InnoDB;

-- Each voucher has 2+ entries; sum(debit) must equal sum(credit) — enforced in application layer
CREATE TABLE voucher_entries (
    entry_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    voucher_id          BIGINT NOT NULL,
    ledger_id           INT NOT NULL,
    cost_center_id       INT NULL,
    debit_amount        DECIMAL(18,2) DEFAULT 0.00,
    credit_amount       DECIMAL(18,2) DEFAULT 0.00,
    entry_narration     VARCHAR(300),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    FOREIGN KEY (ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (cost_center_id) REFERENCES cost_centers(cost_center_id) ON DELETE SET NULL,
    CHECK ( (debit_amount = 0 AND credit_amount > 0) OR (credit_amount = 0 AND debit_amount > 0) )
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. INVENTORY (Stock Groups, Items, Units, Godowns)
-- ------------------------------------------------------------
CREATE TABLE units_of_measure (
    unit_id             INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(20) NOT NULL,     -- Nos, Kg, Ltr, Box
    symbol              VARCHAR(10) NOT NULL,
    decimal_places      TINYINT DEFAULT 2,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE stock_groups (
    stock_group_id      INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(100) NOT NULL,
    parent_id           INT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES stock_groups(stock_group_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE godowns (
    godown_id           INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(100) NOT NULL,
    address             VARCHAR(300),
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE stock_items (
    stock_item_id       INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(150) NOT NULL,
    stock_group_id      INT,
    unit_id             INT NOT NULL,
    hsn_code            VARCHAR(10),               -- for GST
    gst_rate_percent    DECIMAL(5,2) DEFAULT 0.00,
    opening_qty         DECIMAL(14,3) DEFAULT 0,
    opening_rate        DECIMAL(14,2) DEFAULT 0,
    reorder_level       DECIMAL(14,3) DEFAULT 0,
    is_active           BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_group_id) REFERENCES stock_groups(stock_group_id) ON DELETE SET NULL,
    FOREIGN KEY (unit_id) REFERENCES units_of_measure(unit_id)
) ENGINE=InnoDB;

-- Inventory movement tied to a voucher (e.g. Sales voucher reduces stock)
CREATE TABLE stock_entries (
    stock_entry_id      BIGINT AUTO_INCREMENT PRIMARY KEY,
    voucher_id          BIGINT NOT NULL,
    stock_item_id       INT NOT NULL,
    godown_id           INT NOT NULL,
    quantity            DECIMAL(14,3) NOT NULL,      -- positive = inward, negative = outward
    rate                DECIMAL(14,2) NOT NULL,
    amount              DECIMAL(18,2) NOT NULL,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    FOREIGN KEY (stock_item_id) REFERENCES stock_items(stock_item_id),
    FOREIGN KEY (godown_id) REFERENCES godowns(godown_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 6. GST DETAILS (tax ledgers linked to invoices)
-- ------------------------------------------------------------
CREATE TABLE tax_rates (
    tax_rate_id         INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(50) NOT NULL,     -- GST 5%, GST 12%, GST 18%, GST 28%
    cgst_percent        DECIMAL(5,2) DEFAULT 0,
    sgst_percent        DECIMAL(5,2) DEFAULT 0,
    igst_percent        DECIMAL(5,2) DEFAULT 0,
    cess_percent        DECIMAL(5,2) DEFAULT 0,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 7. BANK RECONCILIATION
-- ------------------------------------------------------------
CREATE TABLE bank_reconciliations (
    reco_id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    voucher_entry_id    BIGINT NOT NULL,
    bank_date           DATE,
    is_reconciled       BOOLEAN DEFAULT FALSE,
    reconciled_at       TIMESTAMP NULL,
    FOREIGN KEY (voucher_entry_id) REFERENCES voucher_entries(entry_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 8. BUDGETS
-- ------------------------------------------------------------
CREATE TABLE budgets (
    budget_id           INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    fy_id               INT NOT NULL,
    ledger_id           INT NOT NULL,
    cost_center_id      INT NULL,
    budgeted_amount     DECIMAL(18,2) NOT NULL,
    period              ENUM('Monthly','Quarterly','Yearly') DEFAULT 'Yearly',
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (fy_id) REFERENCES financial_years(fy_id) ON DELETE CASCADE,
    FOREIGN KEY (ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (cost_center_id) REFERENCES cost_centers(cost_center_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 9. AUDIT LOG (who changed what, when — required for staff-level
--    systems and for Tally's "Edit Log" feature)
-- ------------------------------------------------------------
CREATE TABLE audit_logs (
    audit_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    user_id             INT NOT NULL,
    action              VARCHAR(20) NOT NULL,     -- CREATE, UPDATE, DELETE, CANCEL
    entity_type         VARCHAR(50) NOT NULL,     -- voucher, ledger, stock_item, user, etc.
    entity_id           BIGINT NOT NULL,
    old_value           JSON,
    new_value           JSON,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Helpful indexes for reporting performance
-- ------------------------------------------------------------
CREATE INDEX idx_voucher_date ON vouchers (company_id, voucher_date);
CREATE INDEX idx_voucher_entries_ledger ON voucher_entries (ledger_id);
CREATE INDEX idx_stock_entries_item ON stock_entries (stock_item_id, godown_id);
CREATE INDEX idx_ledgers_group ON ledgers (group_id);
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id);

SET FOREIGN_KEY_CHECKS = 1;
