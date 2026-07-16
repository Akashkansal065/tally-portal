-- ============================================================
-- Open Tally-Clone : Schema Extension — Payroll
-- Depends on: schema.sql (companies, ledgers, vouchers, users)
-- ============================================================

SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------------------------------------
-- 1. EMPLOYEES
-- ------------------------------------------------------------
-- Deliberately NOT tied to `users` — most employees (factory staff,
-- field workers) never log into the system at all. A `linked_user_id`
-- is optional, for the subset who also need app access.
CREATE TABLE employees (
    employee_id         INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    linked_user_id       INT NULL,
    employee_code       VARCHAR(30) NOT NULL,
    name                VARCHAR(150) NOT NULL,
    designation         VARCHAR(100),
    department          VARCHAR(100),
    date_of_joining     DATE NOT NULL,
    date_of_leaving     DATE NULL,
    pan                 VARCHAR(10),
    uan                 VARCHAR(20),               -- Universal Account Number (PF)
    pf_number           VARCHAR(30),
    esi_number          VARCHAR(30),
    bank_account_no     VARCHAR(30),
    bank_ifsc           VARCHAR(15),
    payment_ledger_id   INT NOT NULL,               -- ledger used for salary payable/paid entries (per-employee or shared)
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (linked_user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (payment_ledger_id) REFERENCES ledgers(ledger_id),
    UNIQUE KEY uq_employee_code (company_id, employee_code)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. SALARY COMPONENTS (reusable building blocks: Basic, HRA, PF, etc.)
-- ------------------------------------------------------------
CREATE TABLE salary_components (
    component_id        INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    name                VARCHAR(60) NOT NULL,       -- Basic, HRA, Conveyance, PF Employee, ESI Employee, Professional Tax
    component_type      ENUM('Earning','Deduction') NOT NULL,
    calculation_type    ENUM('Fixed','Percent of Basic','Formula') DEFAULT 'Fixed',
    percent_of_basic    DECIMAL(5,2) NULL,          -- used when calculation_type = 'Percent of Basic'
    is_statutory        BOOLEAN DEFAULT FALSE,       -- PF/ESI/PT flagged so payroll reports can isolate them
    linked_ledger_id    INT NOT NULL,                -- expense or liability ledger this component posts to
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (linked_ledger_id) REFERENCES ledgers(ledger_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. SALARY STRUCTURES (per-employee, versioned by effective date —
--    a raise or role change creates a new row, not an overwrite)
-- ------------------------------------------------------------
CREATE TABLE salary_structures (
    structure_id        INT AUTO_INCREMENT PRIMARY KEY,
    employee_id         INT NOT NULL,
    effective_from      DATE NOT NULL,
    effective_to        DATE NULL,                  -- NULL = currently active
    ctc_annual          DECIMAL(18,2) NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE salary_structure_components (
    structure_component_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    structure_id            INT NOT NULL,
    component_id             INT NOT NULL,
    amount                   DECIMAL(18,2) NOT NULL, -- resolved monthly amount (computed at structure-creation time from % rules)
    FOREIGN KEY (structure_id) REFERENCES salary_structures(structure_id) ON DELETE CASCADE,
    FOREIGN KEY (component_id) REFERENCES salary_components(component_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. PAYROLL PERIODS & PAYSLIPS
-- ------------------------------------------------------------
CREATE TABLE payroll_periods (
    period_id           INT AUTO_INCREMENT PRIMARY KEY,
    company_id          INT NOT NULL,
    period_month        TINYINT NOT NULL,           -- 1-12
    period_year         SMALLINT NOT NULL,
    status              ENUM('Draft','Processed','Paid','Locked') DEFAULT 'Draft',
    processed_at        TIMESTAMP NULL,
    processed_by        INT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (processed_by) REFERENCES users(user_id),
    UNIQUE KEY uq_period (company_id, period_month, period_year)
) ENGINE=InnoDB;

CREATE TABLE payslips (
    payslip_id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    period_id            INT NOT NULL,
    employee_id          INT NOT NULL,
    days_present         DECIMAL(4,1) NOT NULL,
    days_in_period       TINYINT NOT NULL,
    gross_earnings       DECIMAL(18,2) NOT NULL,
    total_deductions     DECIMAL(18,2) NOT NULL,
    net_pay              DECIMAL(18,2) NOT NULL,
    voucher_id           BIGINT NULL,                -- Journal voucher posting salary expense/payable (schema.sql vouchers)
    payment_voucher_id   BIGINT NULL,                -- Payment voucher once actually disbursed
    generated_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (period_id) REFERENCES payroll_periods(period_id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    FOREIGN KEY (payment_voucher_id) REFERENCES vouchers(voucher_id) ON DELETE SET NULL,
    UNIQUE KEY uq_payslip (period_id, employee_id)
) ENGINE=InnoDB;

CREATE TABLE payslip_components (
    payslip_component_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    payslip_id           BIGINT NOT NULL,
    component_id          INT NOT NULL,
    amount                DECIMAL(18,2) NOT NULL,
    FOREIGN KEY (payslip_id) REFERENCES payslips(payslip_id) ON DELETE CASCADE,
    FOREIGN KEY (component_id) REFERENCES salary_components(component_id)
) ENGINE=InnoDB;

CREATE INDEX idx_employees_active ON employees (company_id, is_active);
CREATE INDEX idx_payslips_period ON payslips (period_id);

SET FOREIGN_KEY_CHECKS = 1;

-- ------------------------------------------------------------
-- Application flow:
-- 1. Admin runs "Process Payroll" for a period -> for each active
--    employee, resolve their active salary_structure as of that month,
--    compute attendance-adjusted amounts -> insert payslips + payslip_components.
-- 2. On confirm: auto-create ONE Journal voucher per period (not per
--    employee) debiting Salary Expense components, crediting a
--    "Salaries Payable" liability ledger -> payroll_periods.status = 'Processed'.
-- 3. On actual bank disbursement: create Payment voucher(s) debiting
--    Salaries Payable, crediting Bank -> payslips.payment_voucher_id set,
--    payroll_periods.status = 'Paid'.
-- 4. payroll_periods.status = 'Locked' prevents further edits once
--    statutory filings (PF/ESI returns) are done for that period.
-- ------------------------------------------------------------
