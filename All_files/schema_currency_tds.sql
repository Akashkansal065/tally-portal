-- ============================================================
-- Open Tally-Clone : Schema Extension — Multi-Currency & TDS/TCS
-- Depends on: schema.sql (ledgers, vouchers, voucher_entries, companies)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ================================================================
-- PART A — MULTI-CURRENCY
-- ================================================================

CREATE TABLE currencies (
    currency_id         INT AUTO_INCREMENT PRIMARY KEY,
    code                VARCHAR(3) NOT NULL UNIQUE,     -- USD, EUR, GBP, AED
    symbol              VARCHAR(10) NOT NULL,
    decimal_places      TINYINT DEFAULT 2,
    is_base_currency    BOOLEAN DEFAULT FALSE            -- exactly one TRUE per company in practice; enforced in app layer
) ENGINE=InnoDB;

CREATE TABLE exchange_rates (
    rate_id             BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    currency_id         INT NOT NULL,
    rate_date           DATE NOT NULL,
    rate_to_base        DECIMAL(14,6) NOT NULL,          -- 1 unit of currency = X units of base currency
    source              ENUM('Manual','RBI','API') DEFAULT 'Manual',
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (currency_id) REFERENCES currencies(currency_id),
    UNIQUE KEY uq_rate_date (company_id, currency_id, rate_date)
) ENGINE=InnoDB;

-- A ledger CAN optionally operate in a foreign currency (e.g. an
-- overseas customer/vendor). NULL currency_id = base currency only.
ALTER TABLE ledgers
    ADD COLUMN currency_id INT NULL AFTER opening_balance_type,
    ADD CONSTRAINT fk_ledger_currency FOREIGN KEY (currency_id) REFERENCES currencies(currency_id);

-- Every voucher_entries row records the base-currency amount already
-- (debit_amount/credit_amount). These columns capture the ORIGINAL
-- foreign-currency amount and the rate used, so forex gain/loss can be
-- computed later without losing precision or context.
ALTER TABLE voucher_entries
    ADD COLUMN forex_currency_id INT NULL AFTER credit_amount,
    ADD COLUMN forex_amount DECIMAL(18,4) NULL AFTER forex_currency_id,
    ADD COLUMN exchange_rate_used DECIMAL(14,6) NULL AFTER forex_amount,
    ADD CONSTRAINT fk_entry_forex_currency FOREIGN KEY (forex_currency_id) REFERENCES currencies(currency_id);

-- Realized/unrealized forex gain-loss adjustments (e.g. when a foreign
-- invoice raised at one rate is settled at another — the difference
-- posts to a Forex Gain/Loss ledger via a Journal voucher).
CREATE TABLE forex_adjustments (
    adjustment_id       BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    bill_id             BIGINT NOT NULL,             -- from schema_orders_payments.sql
    original_rate       DECIMAL(14,6) NOT NULL,
    settlement_rate     DECIMAL(14,6) NOT NULL,
    gain_loss_amount    DECIMAL(18,2) NOT NULL,       -- positive = gain, negative = loss
    adjustment_type     ENUM('Realized','Unrealized') NOT NULL,
    voucher_id          BIGINT NULL,                  -- Journal voucher posting the adjustment
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL
) ENGINE=InnoDB;

-- ================================================================
-- PART B — TDS (Tax Deducted at Source) & TCS (Tax Collected at Source)
-- ================================================================

-- Standard Indian TDS sections (194C, 194J, 194Q etc.) — seed data,
-- company can add custom ones.
CREATE TABLE tds_sections (
    section_id          INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    section_code        VARCHAR(10) NOT NULL,        -- '194C', '194J', '194Q'
    description         VARCHAR(150) NOT NULL,       -- 'Payment to Contractors', 'Professional Fees'
    default_rate_percent DECIMAL(5,2) NOT NULL,
    threshold_limit     DECIMAL(18,2) DEFAULT 0,     -- TDS applies only above this cumulative amount
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    UNIQUE KEY uq_tds_section (company_id, section_code)
) ENGINE=InnoDB;

CREATE TABLE tcs_sections (
    section_id          INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    section_code        VARCHAR(10) NOT NULL,        -- '206C(1H)'
    description         VARCHAR(150) NOT NULL,
    default_rate_percent DECIMAL(5,2) NOT NULL,
    threshold_limit     DECIMAL(18,2) DEFAULT 0,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    UNIQUE KEY uq_tcs_section (company_id, section_code)
) ENGINE=InnoDB;

-- Some vendors/customers hold a Lower/Nil Deduction Certificate from
-- the tax department — overrides the section's default rate for that party.
CREATE TABLE lower_deduction_certificates (
    certificate_id      INT AUTO_INCREMENT PRIMARY KEY,
    party_ledger_id     INT NOT NULL,
    section_id          INT NOT NULL,
    certificate_number  VARCHAR(50) NOT NULL,
    reduced_rate_percent DECIMAL(5,2) NOT NULL,
    valid_from          DATE NOT NULL,
    valid_to            DATE NOT NULL,
    FOREIGN KEY (party_ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (section_id) REFERENCES tds_sections(section_id)
) ENGINE=InnoDB;

-- Actual deduction/collection recorded against a voucher (e.g. a
-- Purchase voucher for professional fees deducts TDS u/s 194J).
CREATE TABLE tds_tcs_entries (
    entry_id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    entry_type          ENUM('TDS','TCS') NOT NULL,
    voucher_id          BIGINT NOT NULL,
    party_ledger_id     INT NOT NULL,
    section_id          INT NOT NULL,               -- FK resolved against tds_sections OR tcs_sections depending on entry_type (app-layer validated)
    taxable_amount       DECIMAL(18,2) NOT NULL,
    rate_percent_applied DECIMAL(5,2) NOT NULL,      -- resolved rate (section default, or LDC-reduced rate if applicable)
    tax_amount           DECIMAL(18,2) NOT NULL,
    certificate_id       INT NULL,                   -- set if an LDC was applied
    deduction_date        DATE NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE CASCADE,
    FOREIGN KEY (party_ledger_id) REFERENCES ledgers(ledger_id),
    FOREIGN KEY (certificate_id) REFERENCES lower_deduction_certificates(certificate_id)
) ENGINE=InnoDB;

-- Challan details for depositing TDS/TCS to the government — needed
-- for Form 26Q/27Q/27EQ return filing.
CREATE TABLE tax_challans (
    challan_id          INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    entry_type          ENUM('TDS','TCS') NOT NULL,
    challan_number      VARCHAR(30) NOT NULL,
    bsr_code            VARCHAR(10) NOT NULL,
    payment_date        DATE NOT NULL,
    amount              DECIMAL(18,2) NOT NULL,
    quarter             TINYINT NOT NULL,             -- 1-4 (financial year quarter)
    financial_year      VARCHAR(9) NOT NULL,           -- '2026-2027'
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Links individual tds_tcs_entries to the challan that deposited them
CREATE TABLE challan_entry_map (
    map_id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    challan_id          INT NOT NULL,
    entry_id            BIGINT NOT NULL,
    FOREIGN KEY (challan_id) REFERENCES tax_challans(challan_id) ON DELETE CASCADE,
    FOREIGN KEY (entry_id) REFERENCES tds_tcs_entries(entry_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_tds_entries_party ON tds_tcs_entries (party_ledger_id, deduction_date);
CREATE INDEX idx_challan_fy ON tax_challans (company_id, financial_year, quarter);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application flow notes:
-- - When posting a Purchase/Payment voucher against a party ledger that
--   has TDS applicability configured, the app checks lower_deduction_certificates
--   for an active LDC first, else uses tds_sections.default_rate_percent.
-- - TDS deducted reduces the amount actually paid to the vendor and
--   posts to a "TDS Payable" liability ledger via an extra voucher_entries
--   line on the same voucher (not a separate voucher).
-- - Multi-currency: voucher_entries.debit_amount/credit_amount always
--   stay in base currency; forex_amount + exchange_rate_used are display/
--   audit fields. Forex gain/loss only gets realized (posted via
--   forex_adjustments) when a foreign-currency bill is actually settled.
-- ------------------------------------------------------------
