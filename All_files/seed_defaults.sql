-- ============================================================
-- Seed data: default account groups + voucher types
-- Run AFTER inserting a row into `companies` — replace @company_id
-- ============================================================

SET @company_id = 1;  -- change as needed

-- ------------------------------------------------------------
-- Default Primary Groups (mirrors Tally's standard 28 groups)
-- ------------------------------------------------------------
INSERT INTO account_groups (company_id, name, parent_group_id, nature, affects_gross_profit, is_system_defined) VALUES
(@company_id, 'Capital Account',            NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Loans (Liability)',          NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Current Liabilities',        NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Fixed Assets',               NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Investments',                NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Current Assets',             NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Branch / Divisions',         NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Sundry Debtors',             NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Sundry Creditors',           NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Bank Accounts',              NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Cash-in-Hand',               NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Stock-in-Hand',              NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Deposits (Asset)',           NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Loans & Advances (Asset)',   NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Suspense Account',           NULL, 'Asset',     FALSE, TRUE),
(@company_id, 'Duties & Taxes',             NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Provisions',                 NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Reserves & Surplus',         NULL, 'Liability', FALSE, TRUE),
(@company_id, 'Sales Accounts',             NULL, 'Income',    TRUE,  TRUE),
(@company_id, 'Purchase Accounts',          NULL, 'Expense',   TRUE,  TRUE),
(@company_id, 'Direct Income',              NULL, 'Income',    TRUE,  TRUE),
(@company_id, 'Indirect Income',            NULL, 'Income',    FALSE, TRUE),
(@company_id, 'Direct Expenses',            NULL, 'Expense',   TRUE,  TRUE),
(@company_id, 'Indirect Expenses',          NULL, 'Expense',   FALSE, TRUE),
(@company_id, 'Misc. Expenses (Asset)',     NULL, 'Asset',     FALSE, TRUE);

-- ------------------------------------------------------------
-- Default Voucher Types
-- ------------------------------------------------------------
INSERT INTO voucher_types (company_id, name, abbreviation, numbering_method, prefix, next_number, is_system_defined) VALUES
(@company_id, 'Payment',      'Pymt', 'Automatic', 'PYT-', 1, TRUE),
(@company_id, 'Receipt',      'Rcpt', 'Automatic', 'RCT-', 1, TRUE),
(@company_id, 'Contra',       'Ctr',  'Automatic', 'CTR-', 1, TRUE),
(@company_id, 'Journal',      'Jrnl', 'Automatic', 'JRN-', 1, TRUE),
(@company_id, 'Sales',        'Sal',  'Automatic', 'SAL-', 1, TRUE),
(@company_id, 'Purchase',     'Pur',  'Automatic', 'PUR-', 1, TRUE),
(@company_id, 'Debit Note',   'DrN',  'Automatic', 'DN-',  1, TRUE),
(@company_id, 'Credit Note',  'CrN',  'Automatic', 'CN-',  1, TRUE),
(@company_id, 'Stock Journal','StkJ', 'Automatic', 'SJ-',  1, TRUE);

-- ------------------------------------------------------------
-- Default Roles
-- ------------------------------------------------------------
INSERT INTO roles (name, description) VALUES
('Admin',      'Full access to all modules including user management'),
('Accountant', 'Can create/edit vouchers and ledgers, view all reports'),
('DataEntry',  'Can create vouchers only, no edit/delete after posting'),
('Auditor',    'Read-only access to all ledgers, vouchers and reports'),
('Viewer',     'Read-only access to reports only');
