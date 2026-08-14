# TallyPrime API — Complete Voucher Operations (Sales, Purchase, Payment & Receipt) & XML/cURL Integration Guide

This guide is the complete technical reference for all **Sales, Purchase, Payment, and Receipt Voucher Operations** in TallyPrime (Versions 1.0 through 5.0). It documents exact official XML envelope structures, field hierarchies, sign conventions, inventory allocation models, banking transaction allocations, cost centre distributions, tax calculations, and ready-to-run cURL/XML commands for **Create**, **Alter**, **Delete**, and **Pull** operations.

---

## Table of Contents
1. [Core Architecture & Protocol Rules](#1-core-architecture--protocol-rules)
2. [Comparative Accounting Matrix (Sales vs Purchase vs Payment vs Receipt)](#2-comparative-accounting-matrix-sales-vs-purchase-vs-payment-vs-receipt)
3. [Master Field Specifications & Banking / Cost Allocations Hierarchy](#3-master-field-specifications--banking--cost-allocations-hierarchy)
4. [Part I: Sales Voucher Operations](#4-part-i-sales-voucher-operations)
   - [Sales 1: Create Sales Voucher with 18% GST (CGST & SGST)](#sales-1-create-sales-voucher-with-18-gst)
   - [Sales 2: Create Sales Voucher for 0% Tax / Exempt Item (e.g. Decaf Coffee)](#sales-2-create-sales-voucher-for-0-tax--exempt-item)
   - [Sales 3: Create Sales Voucher with Multiple Items, Batches & Godowns](#sales-3-create-sales-voucher-with-multiple-items-batches--godowns)
   - [Sales 4: Alter a Sales Voucher (Change Date to 01-Sep-2025 by GUID/VCHKEY)](#sales-4-alter-a-sales-voucher)
   - [Sales 5: Delete a Sales Voucher](#sales-5-delete-a-sales-voucher)
   - [Sales 6: Pull All Sales Vouchers / Pull for Period](#sales-6-pull-all-sales-vouchers--pull-for-period)
5. [Part II: Purchase Voucher Operations](#5-part-ii-purchase-voucher-operations)
   - [Purchase 1: Create Standard Item Purchase (e.g. Computer US from International Party)](#purchase-1-create-standard-item-purchase)
   - [Purchase 2: Create Purchase Voucher with Custom Date (01-Feb-2026, Qty 10 nos, Bill 'Bill28Pur1')](#purchase-2-create-purchase-voucher-with-custom-date)
   - [Purchase 3: Create Domestic Purchase with GST (100 nos @ ₹15 = ₹1,500 + 4% GST)](#purchase-3-create-domestic-purchase-with-gst)
   - [Purchase 4: Create Domestic Purchase with GST on 01-Aug-2025 (200 nos @ ₹15 = ₹3,000 + 4% GST, Bill 'Bill28PurGST1')](#purchase-4-create-domestic-purchase-with-gst-on-01-aug-2025)
   - [Purchase 5: Alter a Purchase Voucher (Date change, Supplier Bill Reference, Quantity/Rate Alteration)](#purchase-5-alter-a-purchase-voucher)
   - [Purchase 6: Delete a Purchase Voucher](#purchase-6-delete-a-purchase-voucher)
   - [Purchase 7: Pull All Purchase Vouchers (Official TDL Collection)](#purchase-7-pull-all-purchase-vouchers-official-tdl-collection)
   - [Purchase 8: Pull Purchase Vouchers for a Specific Period](#purchase-8-pull-purchase-vouchers-for-a-specific-period)
   - [Purchase 9: Pull Purchase Vouchers for a Single Date](#purchase-9-pull-purchase-vouchers-for-a-single-date)
6. [Part III: Payment Voucher Operations](#6-part-iii-payment-voucher-operations)
   - **Bank Payments (Cheque / NEFT / RTGS)**
     - [Payment 1: Create High-Value Cheque Payment (Import Data Protocol)](#payment-1-create-high-value-cheque-payment-import-data-protocol)
     - [Payment 2: Create Payment with Inter Bank Transfer / NEFT (Rs. 200 on 31-Aug-2025)](#payment-2-create-payment-with-inter-bank-transfer--neft)
     - [Payment 3: Create Payment with Custom Amount (Rs. 900 on 01-Aug-2025 with NEFT)](#payment-3-create-payment-with-custom-amount)
     - [Payment 4: Create Payment with Cheque Banking Allocations (Rs. 200 on 02-Aug-2025)](#payment-4-create-payment-with-cheque-banking-allocations)
   - **Cash Payments & Cost Centre Allocations**
     - [Payment 5: Create Cash Payment for Expenses with Cost Category & Cost Centre (Rs. 100 on 31-Aug-2025)](#payment-5-create-cash-payment-for-expenses-with-cost-category--cost-centre)
     - [Payment 6: Create Cash Payment for Expenses on 01-Aug-2025 (Rs. 500 with Cost Centre)](#payment-6-create-cash-payment-for-expenses-on-01-aug-2025)
     - [Payment 7: Create Cash Payment to Party with Bill Allocations (Rs. 500 on 02-Aug-2025)](#payment-7-create-cash-payment-to-party-with-bill-allocations)
   - **Lifecycle Operations**
     - [Payment 8: Alter a Payment Voucher (Date, Narration, Amount & Bill Allocations)](#payment-8-alter-a-payment-voucher)
     - [Payment 9: Delete a Payment Voucher](#payment-9-delete-a-payment-voucher)
     - [Payment 10: Pull All Payment Vouchers (Official TDL Collection)](#payment-10-pull-all-payment-vouchers-official-tdl-collection)
     - [Payment 11: Pull Payment Vouchers for a Specific Period](#payment-11-pull-payment-vouchers-for-a-specific-period)
     - [Payment 12: Pull Payment Vouchers for a Single Date](#payment-12-pull-payment-vouchers-for-a-single-date)
7. [Part IV: Receipt Voucher Operations](#7-part-iv-receipt-voucher-operations)
   - **Bank Receipts (Cheque / DD / UPI / NEFT)**
     - [Receipt 1: Create Receipt with Cheque / DD (Rs. 2,500 on 31-Aug-2025 from ABC Party)](#receipt-1-create-receipt-with-cheque--dd)
     - [Receipt 2: Create Receipt on 01-Aug-2025 (Rs. 2,500 Cheque/DD)](#receipt-2-create-receipt-on-01-aug-2025)
     - [Receipt 3: Create Receipt with UPI Banking Allocations (Rs. 2,500 on 02-Aug-2025 with VPA)](#receipt-3-create-receipt-with-upi-banking-allocations)
     - [Receipt 4: Create High-Value Cheque Receipt (Import Data Protocol - Rs. 10,00,000 on 20-Mar-2026)](#receipt-4-create-high-value-cheque-receipt-import-data-protocol)
     - [Receipt 5: Create Customer Receipt via Bank Transfer / NEFT (Amar Enterprises)](#receipt-5-create-customer-receipt-via-bank-transfer--neft)
   - **Cash Receipts & Cost Centre Allocations**
     - [Receipt 6: Create Cash Receipt for Income with Cost Category & Cost Centre (Rs. 100 on 31-Aug-2025)](#receipt-6-create-cash-receipt-for-income-with-cost-category--cost-centre)
     - [Receipt 7: Create Cash Receipt for Income on 01-Aug-2025 (Rs. 500 with Cost Centre)](#receipt-7-create-cash-receipt-for-income-on-01-aug-2025)
     - [Receipt 8: Create Cash Receipt from Party with Bill Allocations (ABC Party - Rs. 100 on 02-Aug-2025)](#receipt-8-create-cash-receipt-from-party-with-bill-allocations)
     - [Receipt 9: Create Cash Receipt from Amar Enterprises (Rs. 500 on 02-Aug-2025)](#receipt-9-create-cash-receipt-from-amar-enterprises)
   - **Lifecycle Operations**
     - [Receipt 10: Alter a Receipt Voucher (Date, Narration, Amount & Cost Allocations)](#receipt-10-alter-a-receipt-voucher)
     - [Receipt 11: Delete a Receipt Voucher](#receipt-11-delete-a-receipt-voucher)
     - [Receipt 12: Pull All Receipt Vouchers (Official TDL Collection)](#receipt-12-pull-all-receipt-vouchers-official-tdl-collection)
     - [Receipt 13: Pull Receipt Vouchers for a Specific Period](#receipt-13-pull-receipt-vouchers-for-a-specific-period)
     - [Receipt 14: Pull Receipt Vouchers for a Single Date](#receipt-14-pull-receipt-vouchers-for-a-single-date)
8. [Troubleshooting & Common Pitfalls](#8-troubleshooting--common-pitfalls)

---

## 1. Core Architecture & Protocol Rules

### A. Envelope Selection: `Import` vs `Import Data`
1. **Official TallyPrime API Explorer Protocol (Recommended for Vouchers)**:
   - `<TALLYREQUEST>Import</TALLYREQUEST>`
   - `<TYPE>Data</TYPE>`
   - `<ID>Vouchers</ID>`
   - Requires `<DESC><STATICVARIABLES><SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT><SVCURRENTCOMPANY>Company Name</SVCURRENTCOMPANY></STATICVARIABLES></DESC>`
   - `<VERSION>1</VERSION>` is placed inside `<HEADER>`.

2. **Legacy Masters Protocol**:
   - `<TALLYREQUEST>Import Data</TALLYREQUEST>`
   - Must **NOT** have `<VERSION>1</VERSION>` in `<HEADER>` (otherwise Tally responds with `Unknown Request, cannot be processed`).

---

### B. Mandatory Date Fields
Every voucher record pushed to Tally **strictly requires** three synchronised date tags in `YYYYMMDD` format:
- `<DATE>`: Primary voucher date (e.g. `20250801`).
- `<EFFECTIVEDATE>`: Effective date of accounting/inventory impact.
- `<VCHSTATUSDATE>`: Voucher status lifecycle timestamp.

> ⚠️ **Financial Year Restriction**: The voucher date **must fall within the active financial year** of the company in Tally (e.g. `20250401` to `20260331` for FY 2025–2026). If running in Educational Mode, only dates on the **1st, 2nd, or 31st** of a month are permitted by Tally.

---

## 2. Comparative Accounting Matrix (Sales vs Purchase vs Payment vs Receipt)

| Attribute / Entry Line | Sales Voucher (`VCHTYPE="Sales"`) | Purchase Voucher (`VCHTYPE="Purchase"`) | Payment Voucher (`VCHTYPE="Payment"`) | Receipt Voucher (`VCHTYPE="Receipt"`) |
| :--- | :--- | :--- | :--- | :--- |
| **Party / Beneficiary Ledger** | **Customer (Debtor)**<br>`ISDEEMEDPOSITIVE="Yes"`<br>`ISPARTYLEDGER="Yes"`<br>**Amount is Negative** (`-1180.00` Dr) | **Supplier (Creditor)**<br>`ISDEEMEDPOSITIVE="No"`<br>`ISPARTYLEDGER="Yes"`<br>**Amount is Positive** (`1180.00` Cr) | **Payee / Supplier / Expense**<br>`ISDEEMEDPOSITIVE="Yes"`<br>`ISPARTYLEDGER="Yes"`<br>**Amount is Negative** (`-200.00` Dr) | **Customer / Payee / Income**<br>`ISDEEMEDPOSITIVE="No"`<br>`ISPARTYLEDGER="Yes"`/`"No"`<br>**Amount is Positive** (`1000.00` Cr) |
| **Bank / Cash Ledger** | Bank/Cash Debited (`-ve` Dr) | Not in direct invoice | **Bank / Cash Account**<br>`ISDEEMEDPOSITIVE="No"`<br>`ISPARTYLEDGER="Yes"`/`"No"`<br>**Amount is Positive** (`200.00` Cr) | **Bank / Cash Account**<br>`ISDEEMEDPOSITIVE="Yes"`<br>`ISPARTYLEDGER="Yes"`<br>**Amount is Negative** (`-1000.00` Dr) |
| **Bill Allocations** | `<BILLALLOCATIONS.LIST>` (`-ve` Dr) | `<BILLALLOCATIONS.LIST>` (`+ve` Cr) | `<BILLALLOCATIONS.LIST>` (`-ve` Dr with `Agst Ref`/`New Ref`) | `<BILLALLOCATIONS.LIST>` (`+ve` Cr with `Agst Ref`/`Advance`) |
| **Banking Allocations** | Sourced in Receipt | Sourced in Payment | `<BANKALLOCATIONS.LIST>` with `+ve` Cr amount | `<BANKALLOCATIONS.LIST>` with `+ve` amount |
| **Cost Centre Allocations** | Supported under `<ALLLEDGERENTRIES.LIST>` | Supported under `<ALLLEDGERENTRIES.LIST>` | `<CATEGORYALLOCATIONS.LIST>` $\rightarrow$ `<COSTCENTREALLOCATIONS.LIST>` (`-ve` Dr) | `<CATEGORYALLOCATIONS.LIST>` $\rightarrow$ `<COSTCENTREALLOCATIONS.LIST>` (`+ve` Cr) |
| **Inventory Allocations** | `ISDEEMEDPOSITIVE="No"`<br>**Amount is Positive** | `ISDEEMEDPOSITIVE="Yes"`<br>**Amount is Negative** (`-3000.00`) | Not Applicable (Accounting Only) | Not Applicable (Accounting Only) |
| **Revenue / Expense Account** | `Sales` (`ISDEEMEDPOSITIVE="No"`, `+ve` Cr) | `Purchase` (`ISDEEMEDPOSITIVE="Yes"`, `-ve` Dr) | Direct Party Debit / Expense Debit | Direct Customer Credit / Income Credit |
| **GST Taxes** | Output Liability (`+ve` Cr) | Input Credit ITC (`-ve` Dr) | RCM Tax if applicable | Advance GST Receipt if applicable |

---

## 3. Master Field Specifications & Banking / Cost Allocations Hierarchy

### A. Banking Allocations Specifications (`<BANKALLOCATIONS.LIST>`)
Nested inside `<ALLLEDGERENTRIES.LIST>` for the Bank Ledger entry:

| XML Tag | Data Type | Permitted Values / Description | Example |
| :--- | :--- | :--- | :--- |
| `DATE` | String (`YYYYMMDD`) | Primary transaction date | `20250831` |
| `INSTRUMENTDATE` | String (`YYYYMMDD`) | Date of instrument issue / transfer | `20250831` |
| `TRANSACTIONTYPE` | String | `Cheque/DD`, `UPI`, `Inter Bank Transfer`, `e-Fund Transfer`, `Electronic Cheque`, `Others` | `Cheque/DD` or `UPI` |
| `TRANSFERMODE` | String | `NEFT`, `RTGS`, `IMPS`, `UPI` | `UPI` or `NEFT` |
| `VIRTUALPAYMENTADDRESS` | String | UPI Virtual Payment Address / UPI VPA Handle | `767@okxis` |
| `ISCONNECTEDPAYMENT` | String | `Yes` / `No` (Tally e-Payments connectivity flag) | `No` |
| `PAYMENTMODE` | String | `Transacted`, `Draft`, `Cleared` | `Transacted` |
| `PAYMENTFAVOURING` | String | Beneficiary / Payee / Received From Name | `ABC Party` or `Akshaya Enterprises` |
| `BANKPARTYNAME` | String | Bank Party Name | `ABC Party` |
| `ACCOUNTNUMBER` | String | Bank Account Number | `4891289138912` |
| `IFSCODE` | String | 11-Character IFSC Code | `KKBK0000431` |
| `BANKNAME` | String | Name of Bank | `Kotak Mahindra Bank (India)` |
| `EMAIL` | String | Beneficiary Email ID | `a@gmail.com` |
| `INSTRUMENTNUMBER` | String | Cheque / DD / UTR / Reference Number | `56465787` or `5654654` |
| `CHEQUECROSSCOMMENT`| String | Crossing instruction for cheques (e.g. `A/c Payee`) | `A/c Payee` |
| `AMOUNT` | Float String | Line Amount (`-ve` for Bank Debit in Receipt, `+ve` for Bank Credit in Payment) | `-2500.00` / `200.00` |

---

### B. Cost Category & Cost Centre Allocations (`<CATEGORYALLOCATIONS.LIST>`)
Nested inside `<ALLLEDGERENTRIES.LIST>` for expense or revenue ledgers enabled for Cost Centres:

| XML Tag | Data Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `CATEGORY` | String | Yes | Name of Cost Category | `Primary Cost Category` |
| `ISDEEMEDPOSITIVE` | String | Yes | Same as parent ledger (`Yes` for debit, `No` for credit) | `Yes` |
| `<COSTCENTREALLOCATIONS.LIST>` | List | Yes | Encloses specific cost centres | — |
| `NAME` | String | Yes | Name of Cost Centre master | `Marketing Department` or `CostName` |
| `AMOUNT` | Float String | Yes | Amount allocated to cost centre (`-ve` for Dr, `+ve` for Cr) | `-500.00` |

---

# Part I: Sales Voucher Operations

---

## Sales 1: Create Sales Voucher with 18% GST

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
              <PARTYNAME>Amar Enterprises</PARTYNAME>
              <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
              <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Amar Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-1180.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>INV-2025-001</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-1180.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Sales</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>1000.00</AMOUNT>
               <INVENTORYALLOCATIONS.LIST>
                <STOCKITEMNAME>Apple MacBook Pro Laptop</STOCKITEMNAME>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <RATE>1000.00/nos</RATE>
                <AMOUNT>1000.00</AMOUNT>
                <ACTUALQTY> 1 nos</ACTUALQTY>
                <BILLEDQTY> 1 nos</BILLEDQTY>
                <BATCHALLOCATIONS.LIST>
                 <GODOWNNAME>Main Location</GODOWNNAME>
                 <BATCHNAME>Primary Batch</BATCHNAME>
                 <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
                 <TRACKINGNUMBER>T002</TRACKINGNUMBER>
                 <AMOUNT>1000.00</AMOUNT>
                 <ACTUALQTY> 1 nos</ACTUALQTY>
                 <BILLEDQTY> 1 nos</BILLEDQTY>
                </BATCHALLOCATIONS.LIST>
               </INVENTORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>CGST</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>90.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>SGST</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>90.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Sales 2: Create Sales Voucher for 0% Tax / Exempt Item

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
              <PARTYNAME>Amar Enterprises</PARTYNAME>
              <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
              <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Amar Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-40.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>12</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-40.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Sales</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>40.00</AMOUNT>
               <INVENTORYALLOCATIONS.LIST>
                <STOCKITEMNAME>Decaf Coffee</STOCKITEMNAME>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <RATE>2.00/nos</RATE>
                <AMOUNT>40.00</AMOUNT>
                <ACTUALQTY> 20 nos</ACTUALQTY>
                <BILLEDQTY> 20 nos</BILLEDQTY>
                <BATCHALLOCATIONS.LIST>
                 <GODOWNNAME>Main Location</GODOWNNAME>
                 <BATCHNAME>Primary Batch</BATCHNAME>
                 <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
                 <TRACKINGNUMBER>T001</TRACKINGNUMBER>
                 <AMOUNT>40.00</AMOUNT>
                 <ACTUALQTY> 20 nos</ACTUALQTY>
                 <BILLEDQTY> 20 nos</BILLEDQTY>
                </BATCHALLOCATIONS.LIST>
               </INVENTORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Sales 3: Create Sales Voucher with Multiple Items, Batches & Godowns

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Sales" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
              <PARTYNAME>Amar Enterprises</PARTYNAME>
              <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
              <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Amar Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-2360.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>MULTI-001</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-2360.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Sales</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>2000.00</AMOUNT>
               <INVENTORYALLOCATIONS.LIST>
                <STOCKITEMNAME>Apple MacBook Pro Laptop</STOCKITEMNAME>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <RATE>1000.00/nos</RATE>
                <AMOUNT>1000.00</AMOUNT>
                <ACTUALQTY> 1 nos</ACTUALQTY>
                <BILLEDQTY> 1 nos</BILLEDQTY>
                <BATCHALLOCATIONS.LIST>
                 <GODOWNNAME>Warehouse A</GODOWNNAME>
                 <BATCHNAME>BATCH-MB-01</BATCHNAME>
                 <AMOUNT>1000.00</AMOUNT>
                 <ACTUALQTY> 1 nos</ACTUALQTY>
                 <BILLEDQTY> 1 nos</BILLEDQTY>
                </BATCHALLOCATIONS.LIST>
               </INVENTORYALLOCATIONS.LIST>
               <INVENTORYALLOCATIONS.LIST>
                <STOCKITEMNAME>Hp Pavilion 14 Laptop</STOCKITEMNAME>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <RATE>1000.00/nos</RATE>
                <AMOUNT>1000.00</AMOUNT>
                <ACTUALQTY> 1 nos</ACTUALQTY>
                <BILLEDQTY> 1 nos</BILLEDQTY>
                <BATCHALLOCATIONS.LIST>
                 <GODOWNNAME>Main Location</GODOWNNAME>
                 <BATCHNAME>Primary Batch</BATCHNAME>
                 <AMOUNT>1000.00</AMOUNT>
                 <ACTUALQTY> 1 nos</ACTUALQTY>
                 <BILLEDQTY> 1 nos</BILLEDQTY>
                </BATCHALLOCATIONS.LIST>
               </INVENTORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>CGST</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>180.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>SGST</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>180.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Sales 4: Alter a Sales Voucher

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000090" VCHTYPE="Sales" ACTION="Alter" OBJVIEW="Accounting Voucher View">
              <DATE>20250901</DATE>
              <EFFECTIVEDATE>20250901</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250901</VCHSTATUSDATE>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Sales 5: Delete a Sales Voucher

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Sales" ACTION="Delete">
              <DATE>20250801</DATE>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000059</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Sales 6: Pull All Sales Vouchers / Pull for Period

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>PeriodSalesVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVFROMDATE TYPE="Date">20250401</SVFROMDATE>
        <SVTODATE TYPE="Date">20260331</SVTODATE>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="PeriodSalesVouchers">
            <TYPE>Voucher</TYPE>
            <FETCH>GUID,ALTERID,DATE,VOUCHERTYPENAME,VOUCHERNUMBER,PARTYLEDGERNAME,AMOUNT,ALLLEDGERENTRIES.LIST</FETCH>
            <FILTERS>SalesFilter</FILTERS>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="SalesFilter">
            $VOUCHERTYPENAME = "Sales"
          </SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>'
```

---

# Part II: Purchase Voucher Operations

---

## Purchase 1: Create Standard Item Purchase

Creates an Item Purchase for **Computer US** (20 nos @ ₹10,000 = ₹2,00,000) on date **01st March 2026** from **International Party** with bill reference **12**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
                  <DATE>20260301</DATE>
                  <EFFECTIVEDATE>20260301</EFFECTIVEDATE>
                  <VCHSTATUSDATE>20260301</VCHSTATUSDATE>
                  <GSTREGISTRATIONTYPE>&#4; Unknown</GSTREGISTRATIONTYPE>
                  <STATENAME>Alabama</STATENAME>
                  <COUNTRYOFRESIDENCE>United States of America</COUNTRYOFRESIDENCE>
                  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                  <PARTYNAME>International Party</PARTYNAME>
                  <PARTYLEDGERNAME>International Party</PARTYLEDGERNAME>
                  <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
                  <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
                  <PARTYMAILINGNAME>International Party</PARTYMAILINGNAME>
                  <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
                  <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
                  <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
                  <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
                  <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
                  <BASICBASEPARTYNAME>International Party</BASICBASEPARTYNAME>
                  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                  <ISINVOICE>Yes</ISINVOICE>
                  <ALLINVENTORYENTRIES.LIST>
                   <STOCKITEMNAME>Computer US</STOCKITEMNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <RATE>10000.00/nos</RATE>
                   <AMOUNT>-200000.00</AMOUNT>
                   <ACTUALQTY> 20 nos</ACTUALQTY>
                   <BILLEDQTY> 20 nos</BILLEDQTY>
                   <BATCHALLOCATIONS.LIST>
                    <GODOWNNAME>Main Location</GODOWNNAME>
                    <BATCHNAME>Primary Batch</BATCHNAME>
                    <AMOUNT>-200000.00</AMOUNT>
                    <ACTUALQTY> 20 nos</ACTUALQTY>
                    <BILLEDQTY> 20 nos</BILLEDQTY>
                   </BATCHALLOCATIONS.LIST>
                   <ACCOUNTINGALLOCATIONS.LIST>
                    <LEDGERNAME>Purchase</LEDGERNAME>
                    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                    <ISPARTYLEDGER>No</ISPARTYLEDGER>
                    <AMOUNT>-200000.00</AMOUNT>
                   </ACCOUNTINGALLOCATIONS.LIST>
                  </ALLINVENTORYENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>International Party</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                   <AMOUNT>200000.00</AMOUNT>
                   <BILLALLOCATIONS.LIST>
                    <NAME>12</NAME>
                    <BILLTYPE>New Ref</BILLTYPE>
                    <AMOUNT>200000.00</AMOUNT>
                   </BILLALLOCATIONS.LIST>
                  </LEDGERENTRIES.LIST>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 2: Create Purchase Voucher with Custom Date

Creates a Purchase voucher for **Computer US** (10 nos @ ₹10,000 = ₹1,00,000) on date **01st February 2026** with bill number **Bill28Pur1**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
                  <DATE>20260201</DATE>
                  <EFFECTIVEDATE>20260201</EFFECTIVEDATE>
                  <VCHSTATUSDATE>20260201</VCHSTATUSDATE>
                  <GSTREGISTRATIONTYPE>&#4; Unknown</GSTREGISTRATIONTYPE>
                  <STATENAME>Alabama</STATENAME>
                  <COUNTRYOFRESIDENCE>United States of America</COUNTRYOFRESIDENCE>
                  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                  <PARTYNAME>International Party</PARTYNAME>
                  <PARTYLEDGERNAME>International Party</PARTYLEDGERNAME>
                  <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
                  <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
                  <PARTYMAILINGNAME>International Party</PARTYMAILINGNAME>
                  <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
                  <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
                  <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
                  <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
                  <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
                  <BASICBASEPARTYNAME>International Party</BASICBASEPARTYNAME>
                  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                  <ISINVOICE>Yes</ISINVOICE>
                  <ALLINVENTORYENTRIES.LIST>
                   <STOCKITEMNAME>Computer US</STOCKITEMNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <RATE>10000.00/nos</RATE>
                   <AMOUNT>-100000.00</AMOUNT>
                   <ACTUALQTY> 10 nos</ACTUALQTY>
                   <BILLEDQTY> 10 nos</BILLEDQTY>
                   <BATCHALLOCATIONS.LIST>
                    <GODOWNNAME>Main Location</GODOWNNAME>
                    <BATCHNAME>Primary Batch</BATCHNAME>
                    <AMOUNT>-100000.00</AMOUNT>
                    <ACTUALQTY> 10 nos</ACTUALQTY>
                    <BILLEDQTY> 10 nos</BILLEDQTY>
                   </BATCHALLOCATIONS.LIST>
                   <ACCOUNTINGALLOCATIONS.LIST>
                    <LEDGERNAME>Purchase</LEDGERNAME>
                    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                    <ISPARTYLEDGER>No</ISPARTYLEDGER>
                    <AMOUNT>-100000.00</AMOUNT>
                   </ACCOUNTINGALLOCATIONS.LIST>
                  </ALLINVENTORYENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>International Party</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                   <AMOUNT>100000.00</AMOUNT>
                   <BILLALLOCATIONS.LIST>
                    <NAME>Bill28Pur1</NAME>
                    <BILLTYPE>New Ref</BILLTYPE>
                    <AMOUNT>100000.00</AMOUNT>
                   </BILLALLOCATIONS.LIST>
                  </LEDGERENTRIES.LIST>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 3: Create Domestic Purchase with GST

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
                  <DATE>20250901</DATE>
                  <EFFECTIVEDATE>20250901</EFFECTIVEDATE>
                  <VCHSTATUSDATE>20250901</VCHSTATUSDATE>
                  <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
                  <VATDEALERTYPE>Regular</VATDEALERTYPE>
                  <STATENAME>Karnataka</STATENAME>
                  <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
                  <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>
                  <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
                  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                  <PARTYNAME>Mondal Enterprises</PARTYNAME>
                  <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>
                  <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>
                  <PARTYLEDGERNAME>Mondal Enterprises</PARTYLEDGERNAME>
                  <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
                  <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
                  <PARTYMAILINGNAME>Mondal Enterprises</PARTYMAILINGNAME>
                  <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
                  <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
                  <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
                  <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
                  <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
                  <BASICBASEPARTYNAME>Mondal Enterprises</BASICBASEPARTYNAME>
                  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                  <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>
                  <ISINVOICE>Yes</ISINVOICE>
                  <ALLINVENTORYENTRIES.LIST>
                   <STOCKITEMNAME>Decaf Coffee</STOCKITEMNAME>
                   <GSTOVRDNINELIGIBLEITC>&#4; Not Applicable</GSTOVRDNINELIGIBLEITC>
                   <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>
                   <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>
                   <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>
                   <GSTITEMSOURCE>Decaf Coffee</GSTITEMSOURCE>
                   <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>
                   <HSNITEMSOURCE>Decaf Coffee</HSNITEMSOURCE>
                   <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>
                   <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>
                   <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <RATE>15.00/nos</RATE>
                   <AMOUNT>-1500.00</AMOUNT>
                   <ACTUALQTY> 100 nos</ACTUALQTY>
                   <BILLEDQTY> 100 nos</BILLEDQTY>
                   <BATCHALLOCATIONS.LIST>
                    <GODOWNNAME>Main Location</GODOWNNAME>
                    <BATCHNAME>Primary Batch</BATCHNAME>
                    <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
                    <AMOUNT>-1500.00</AMOUNT>
                    <ACTUALQTY> 100 nos</ACTUALQTY>
                    <BILLEDQTY> 100 nos</BILLEDQTY>
                   </BATCHALLOCATIONS.LIST>
                   <ACCOUNTINGALLOCATIONS.LIST>
                    <LEDGERNAME>GST Purchase</LEDGERNAME>
                    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                    <ISPARTYLEDGER>No</ISPARTYLEDGER>
                    <AMOUNT>-1500.00</AMOUNT>
                   </ACCOUNTINGALLOCATIONS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 2</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 2</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 4</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>
                   </RATEDETAILS.LIST>
                  </ALLINVENTORYENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>Mondal Enterprises</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                   <AMOUNT>1560.00</AMOUNT>
                   <BILLALLOCATIONS.LIST>
                    <NAME>23</NAME>
                    <BILLTYPE>New Ref</BILLTYPE>
                    <AMOUNT>1560.00</AMOUNT>
                   </BILLALLOCATIONS.LIST>
                  </LEDGERENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>CGST</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>No</ISPARTYLEDGER>
                   <AMOUNT>-30.00</AMOUNT>
                  </LEDGERENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>SGST</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>No</ISPARTYLEDGER>
                   <AMOUNT>-30.00</AMOUNT>
                  </LEDGERENTRIES.LIST>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 4: Create Domestic Purchase with GST on 01-Aug-2025

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View">
                  <DATE>20250801</DATE>
                  <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
                  <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
                  <GSTREGISTRATIONTYPE>Regular</GSTREGISTRATIONTYPE>
                  <VATDEALERTYPE>Regular</VATDEALERTYPE>
                  <STATENAME>Karnataka</STATENAME>
                  <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
                  <PARTYGSTIN>29AAACH1004N1ZQ</PARTYGSTIN>
                  <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
                  <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
                  <PARTYNAME>Mondal Enterprises</PARTYNAME>
                  <GSTREGISTRATION TAXTYPE="GST" TAXREGISTRATION="29AAECP4424C1ZN">Karnataka Registration</GSTREGISTRATION>
                  <CMPGSTIN>29AAECP4424C1ZN</CMPGSTIN>
                  <PARTYLEDGERNAME>Mondal Enterprises</PARTYLEDGERNAME>
                  <BASICBUYERNAME>Bhrama Enterprises</BASICBUYERNAME>
                  <CMPGSTREGISTRATIONTYPE>Regular</CMPGSTREGISTRATIONTYPE>
                  <PARTYMAILINGNAME>Mondal Enterprises</PARTYMAILINGNAME>
                  <CONSIGNEEGSTIN>29AAECP4424C1ZN</CONSIGNEEGSTIN>
                  <CONSIGNEEMAILINGNAME>Bhrama Enterprises</CONSIGNEEMAILINGNAME>
                  <CONSIGNEESTATENAME>Karnataka</CONSIGNEESTATENAME>
                  <CMPGSTSTATE>Karnataka</CMPGSTSTATE>
                  <CONSIGNEECOUNTRYNAME>India</CONSIGNEECOUNTRYNAME>
                  <BASICBASEPARTYNAME>Mondal Enterprises</BASICBASEPARTYNAME>
                  <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
                  <VCHENTRYMODE>Item Invoice</VCHENTRYMODE>
                  <ISINVOICE>Yes</ISINVOICE>
                  <ALLINVENTORYENTRIES.LIST>
                   <STOCKITEMNAME>Decaf Coffee</STOCKITEMNAME>
                   <GSTOVRDNINELIGIBLEITC>&#4; Not Applicable</GSTOVRDNINELIGIBLEITC>
                   <GSTOVRDNISREVCHARGEAPPL>&#4; Not Applicable</GSTOVRDNISREVCHARGEAPPL>
                   <GSTOVRDNTAXABILITY>Taxable</GSTOVRDNTAXABILITY>
                   <GSTSOURCETYPE>Stock Item</GSTSOURCETYPE>
                   <GSTITEMSOURCE>Decaf Coffee</GSTITEMSOURCE>
                   <HSNSOURCETYPE>Stock Item</HSNSOURCETYPE>
                   <HSNITEMSOURCE>Decaf Coffee</HSNITEMSOURCE>
                   <GSTOVRDNTYPEOFSUPPLY>Goods</GSTOVRDNTYPEOFSUPPLY>
                   <GSTRATEINFERAPPLICABILITY>As per Masters/Company</GSTRATEINFERAPPLICABILITY>
                   <GSTHSNINFERAPPLICABILITY>As per Masters/Company</GSTHSNINFERAPPLICABILITY>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <RATE>15.00/nos</RATE>
                   <AMOUNT>-3000.00</AMOUNT>
                   <ACTUALQTY> 200 nos</ACTUALQTY>
                   <BILLEDQTY> 200 nos</BILLEDQTY>
                   <BATCHALLOCATIONS.LIST>
                    <GODOWNNAME>Main Location</GODOWNNAME>
                    <BATCHNAME>Primary Batch</BATCHNAME>
                    <DESTINATIONGODOWNNAME>Main Location</DESTINATIONGODOWNNAME>
                    <AMOUNT>-3000.00</AMOUNT>
                    <ACTUALQTY> 200 nos</ACTUALQTY>
                    <BILLEDQTY> 200 nos</BILLEDQTY>
                   </BATCHALLOCATIONS.LIST>
                   <ACCOUNTINGALLOCATIONS.LIST>
                    <LEDGERNAME>GST Purchase</LEDGERNAME>
                    <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                    <ISPARTYLEDGER>No</ISPARTYLEDGER>
                    <AMOUNT>-3000.00</AMOUNT>
                   </ACCOUNTINGALLOCATIONS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 2</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 2</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                    <GSTRATE> 4</GSTRATE>
                   </RATEDETAILS.LIST>
                   <RATEDETAILS.LIST>
                    <GSTRATEDUTYHEAD>Cess</GSTRATEDUTYHEAD>
                    <GSTRATEVALUATIONTYPE>&#4; Not Applicable</GSTRATEVALUATIONTYPE>
                   </RATEDETAILS.LIST>
                  </ALLINVENTORYENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>Mondal Enterprises</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                   <AMOUNT>3120.00</AMOUNT>
                   <BILLALLOCATIONS.LIST>
                    <NAME>Bill28PurGST1</NAME>
                    <BILLTYPE>New Ref</BILLTYPE>
                    <AMOUNT>3120.00</AMOUNT>
                   </BILLALLOCATIONS.LIST>
                  </LEDGERENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>CGST</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>No</ISPARTYLEDGER>
                   <AMOUNT>-60.00</AMOUNT>
                  </LEDGERENTRIES.LIST>
                  <LEDGERENTRIES.LIST>
                   <LEDGERNAME>SGST</LEDGERNAME>
                   <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                   <ISPARTYLEDGER>No</ISPARTYLEDGER>
                   <AMOUNT>-60.00</AMOUNT>
                  </LEDGERENTRIES.LIST>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 5: Alter a Purchase Voucher

### Example A: Base Purchase Alteration (Change Date to `02nd August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8" VCHTYPE="Purchase" ACTION="Alter" OBJVIEW="Invoice Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000079</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example B: Alter Purchase Voucher Date to `1st March 2026`
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010" VCHTYPE="Purchase" ACTION="Alter" OBJVIEW="Invoice Voucher View">
                <DATE>20260301</DATE>
                <EFFECTIVEDATE>20260301</EFFECTIVEDATE>
                <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083</GUID>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example C: Alter Item Quantity to `15 nos` with Full Amount Recalculation
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010" VCHTYPE="Purchase" ACTION="Alter" OBJVIEW="Invoice Voucher View">
                <DATE>20260301</DATE>
                <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083</GUID>
                <ALLINVENTORYENTRIES.LIST>
                 <STOCKITEMNAME>Computer US</STOCKITEMNAME>
                 <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                 <RATE>10000.00/nos</RATE>
                 <AMOUNT>-150000.00</AMOUNT>
                 <ACTUALQTY> 15 nos</ACTUALQTY>
                 <BILLEDQTY> 15 nos</BILLEDQTY>
                 <BATCHALLOCATIONS.LIST>
                  <GODOWNNAME>Main Location</GODOWNNAME>
                  <BATCHNAME>Primary Batch</BATCHNAME>
                  <AMOUNT>-150000.00</AMOUNT>
                  <ACTUALQTY> 15 nos</ACTUALQTY>
                  <BILLEDQTY> 15 nos</BILLEDQTY>
                 </BATCHALLOCATIONS.LIST>
                 <ACCOUNTINGALLOCATIONS.LIST>
                  <LEDGERNAME>Purchase</LEDGERNAME>
                  <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                  <ISPARTYLEDGER>No</ISPARTYLEDGER>
                  <AMOUNT>-150000.00</AMOUNT>
                 </ACCOUNTINGALLOCATIONS.LIST>
                </ALLINVENTORYENTRIES.LIST>
                <LEDGERENTRIES.LIST>
                 <LEDGERNAME>International Party</LEDGERNAME>
                 <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                 <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
                 <AMOUNT>150000.00</AMOUNT>
                 <BILLALLOCATIONS.LIST>
                  <NAME>Bill28Pur1</NAME>
                  <BILLTYPE>New Ref</BILLTYPE>
                  <AMOUNT>150000.00</AMOUNT>
                 </BILLALLOCATIONS.LIST>
                </LEDGERENTRIES.LIST>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 6: Delete a Purchase Voucher

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b400:00000010" VCHTYPE="Purchase" ACTION="Delete" OBJVIEW="Invoice Voucher View">
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000083</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 7: Pull All Purchase Vouchers (Official TDL Collection)

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Purchase Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL All Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePurchase</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                </COLLECTION>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 8: Pull Purchase Vouchers for a Specific Period

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Purchase Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePurchase</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date &gt;= ($$Date:"01-07-2025") AND $Date &lt;= ($$Date:"10-07-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Purchase 9: Pull Purchase Vouchers for a Single Date

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Purchase Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Purchase Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePurchase</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date = ($$Date:"02-04-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

# Part III: Payment Voucher Operations

---

## 1. Overview & Accounting Concepts

A **Payment Voucher** is used to record all outgoing disbursements made by the business, whether through cash, bank transfer, cheque, or other payment modes. It captures transactions where money is paid to suppliers (creditors), employees (salaries/advances), statutory tax liabilities, or for business overhead expenses (rent, electricity, advertising), ensuring proper tracking and reconciliation of financial cash outflows.

### Financial Ledger Impact:
Each payment transaction impacts at least two ledgers:
1. **Source Ledger (Cash / Bank Account)**: **Credited** (`ISDEEMEDPOSITIVE="No"`, positive amount in XML) representing the outflow of liquid assets.
2. **Destination Ledger (Expense / Party / Liability)**: **Debited** (`ISDEEMEDPOSITIVE="Yes"`, negative amount in XML) representing the expense incurred or clearance of payable liability.

---

## 2. Payment Voucher Master Tag Specifications

| Tag | Mandatory | Data Type | Permitted Values / Description |
| :--- | :--- | :--- | :--- |
| `VOUCHERTYPENAME` / `VCHTYPE` | **Yes** | String | Defines the voucher type master under which the entry is recorded. Must be `Payment` (or custom subtype under Payment). |
| `DATE` | **Yes** | String (`YYYYMMDD`)| Primary transaction date in Tally format (e.g. `20260320`). |
| `EFFECTIVEDATE` | **Yes** | String (`YYYYMMDD`)| Date on which financial / bank impact takes effect. |
| `VCHSTATUSDATE` | **Yes** | String (`YYYYMMDD`)| Lifecycle status timestamp. |
| `VOUCHERNUMBER` | Conditional | String | Custom voucher sequence / cheque serial number. If omitted, Tally auto-generates sequential numbering. |
| `PARTYNAME` / `PARTYLEDGERNAME` | **Yes** | String | Primary bank / cash account or beneficiary party involved in the transaction. |
| `COUNTRYOFRESIDENCE` | Optional | String | Payee / Company Country (e.g. `India`). |
| `PLACEOFSUPPLY` | Optional | String | State name for GST state compliance (e.g. `Karnataka`). |
| `ALLLEDGERENTRIES.LIST` | **Yes** | Collection | Collection of all debit and credit ledger rows forming the balanced double-entry transaction. |
| `LEDGERNAME` | **Yes** | String | Exact name of the ledger master in Tally (e.g. `Advertising Expenses`, `Bank of Baroda`, `Cash`). |
| `ISDEEMEDPOSITIVE` | **Yes** | Logical / String | `Yes` for **Debit** (Expense / Party payment), `No` for **Credit** (Cash / Bank account). |
| `ISPARTYLEDGER` | **Yes** | Logical / String | `Yes` if the line represents the primary party / bank, `No` for internal expense accounts. |
| `AMOUNT` | **Yes** | Float String | Transaction amount (**Negative for Debit**, **Positive for Credit**). |
| `BANKALLOCATIONS.LIST` | Banking | Collection | Encloses electronic transfer or cheque clearing parameters. |
| `CATEGORYALLOCATIONS.LIST` | Cost Centres | Collection | Encloses cost category and cost centre distribution. |
| `BILLALLOCATIONS.LIST` | Bills | Collection | Encloses bill reference (`New Ref` / `Agst Ref` / `Advance`). |

---

## 3. Envelope Protocols for Payment Vouchers

Tally accepts payment vouchers via two XML envelope formats:

1. **Standard API Explorer Envelope (`Import Vouchers`)**:
   - `<TALLYREQUEST>Import</TALLYREQUEST>`
   - `<TYPE>Data</TYPE>`
   - `<ID>Vouchers</ID>`
   - Wrapped in `<DESC><STATICVARIABLES><SVCURRENTCOMPANY>...</SVCURRENTCOMPANY></STATICVARIABLES></DESC><DATA><TALLYMESSAGE>...`

2. **Direct Data Import Envelope (`Import Data`)**:
   - `<TALLYREQUEST>Import Data</TALLYREQUEST>`
   - Wrapped in `<BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE>...` (without `<VERSION>1</VERSION>` in header).

---

## Payment 1: Create High-Value Cheque Payment (Import Data Protocol)

Creates a Payment Voucher on date **20th March 2026** paying **₹10,00,000.00** for **Advertising Expenses** via **Bank of Baroda** with cheque crossing (`A/c Payee`) and voucher number **32** using the `Import Data` protocol.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
   <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
      <DATE>20260320</DATE>
      <EFFECTIVEDATE>20260320</EFFECTIVEDATE>
      <VCHSTATUSDATE>20260320</VCHSTATUSDATE>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
      <PARTYNAME>Bank of Baroda</PARTYNAME>
      <PARTYLEDGERNAME>Bank of Baroda</PARTYLEDGERNAME>
      <VOUCHERNUMBER>32</VOUCHERNUMBER>
      <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Advertising Expenses</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>-1000000.00</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Bank of Baroda</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>1000000.00</AMOUNT>
       <BANKALLOCATIONS.LIST>
        <DATE>20260320</DATE>
        <INSTRUMENTDATE>20260320</INSTRUMENTDATE>
        <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
        <PAYMENTFAVOURING>Advertising Expenses</PAYMENTFAVOURING>
        <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
        <BANKPARTYNAME>Advertising Expenses</BANKPARTYNAME>
        <AMOUNT>1000000.00</AMOUNT>
       </BANKALLOCATIONS.LIST>
      </ALLLEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>'
```

---

## Payment 2: Create Payment with Inter Bank Transfer / NEFT

Creates a Payment Voucher on date **31st August 2025** for party **Akshaya Enterprises** of amount **₹200.00** paid via **Kotak Bank** with full NEFT electronic banking allocations.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250831</DATE>
              <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-200.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>29</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-200.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>200.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250831</DATE>
                <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
                <EMAIL>a@gmail.com</EMAIL>
                <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
                <IFSCODE>KKBK0000431</IFSCODE>
                <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
                <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
                <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
                <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
                <TRANSFERMODE>NEFT</TRANSFERMODE>
                <INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
                <AMOUNT>200.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 3: Create Payment with Custom Amount

Creates a Payment Voucher on date **01st August 2025** for party **Akshaya Enterprises** of amount **₹900.00** paid via **Kotak Bank** with NEFT.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-900.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>29</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-900.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>900.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250801</DATE>
                <INSTRUMENTDATE>20250828</INSTRUMENTDATE>
                <EMAIL>a@gmail.com</EMAIL>
                <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
                <IFSCODE>KKBK0000431</IFSCODE>
                <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
                <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
                <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
                <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
                <TRANSFERMODE>NEFT</TRANSFERMODE>
                <INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
                <AMOUNT>900.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 4: Create Payment with Cheque Banking Allocations

Creates a Payment Voucher on date **02nd August 2025** for party **Akshaya Enterprises** of amount **₹200.00** paid via **Kotak Bank** with Cheque allocations and `A/c Payee` crossing.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250802</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-200.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>29</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-200.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>200.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250802</DATE>
                <INSTRUMENTDATE>20250802</INSTRUMENTDATE>
                <EMAIL>a@gmail.com</EMAIL>
                <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
                <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
                <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
                <INSTRUMENTNUMBER>7656876878</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
                <AMOUNT>200.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 5: Create Cash Payment for Expenses with Cost Category & Cost Centre

Creates a Cash Payment Voucher on date **31st August 2025** for **Sundry Expenses** of amount **₹100.00** with cost allocations under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250831</DATE>
              <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Sundry Expenses</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>-100.00</AMOUNT>
               <CATEGORYALLOCATIONS.LIST>
                <CATEGORY>Primary Cost Category</CATEGORY>
                <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                <COSTCENTREALLOCATIONS.LIST>
                 <NAME>CostName</NAME>
                 <AMOUNT>-100.00</AMOUNT>
                </COSTCENTREALLOCATIONS.LIST>
               </CATEGORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>100.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 6: Create Cash Payment for Expenses on 01-Aug-2025

Creates a Cash Payment Voucher on date **01st August 2025** for **Sundry Expenses** of amount **₹500.00** with cost allocations under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Sundry Expenses</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>-500.00</AMOUNT>
               <CATEGORYALLOCATIONS.LIST>
                <CATEGORY>Primary Cost Category</CATEGORY>
                <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
                <COSTCENTREALLOCATIONS.LIST>
                 <NAME>CostName</NAME>
                 <AMOUNT>-500.00</AMOUNT>
                </COSTCENTREALLOCATIONS.LIST>
               </CATEGORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 7: Create Cash Payment to Party with Bill Allocations

Creates a Cash Payment Voucher on date **02nd August 2025** paying supplier **Akshaya Enterprises** amount **₹500.00** in cash with bill reference **Bill30AugAE** (`New Ref`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Payment" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250802</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-500.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>Bill30AugAE</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-500.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Payment 8: Alter a Payment Voucher

Altering a Payment Voucher in Tally requires identifying the existing record using its unique identifier (`GUID`, `REMOTEID`, or `VCHKEY`).

### Example A: Base Payment Alteration (Change Date to `01st August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Alter" OBJVIEW="Accounting Voucher View">
                <DATE>20250801</DATE>
                <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example B: Alter Payment Voucher Date to `1st September 2025`
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
              <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Alter" OBJVIEW="Accounting Voucher View">
                <DATE>20250901</DATE>
                <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
              </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example C: Alter Payment Debit & Credit Amount Values to `₹250.00`
Alters both the party debit ledger and the cash credit ledger to `₹250.00`, with updated bill allocation `Bill30AugAE`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Alter" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Akshaya Enterprises</PARTYLEDGERNAME>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Akshaya Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-250.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>Bill30AugAE</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>-250.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>250.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Expected Success Response for Alter
```xml
<ENVELOPE>
 <HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <ERRORS>0</ERRORS>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
 </BODY>
</ENVELOPE>
```

---

## Payment 9: Delete a Payment Voucher

Deletes a specific payment voucher by `GUID`, `REMOTEID`, or `VCHKEY`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b348:00000058" VCHTYPE="Payment" ACTION="Delete" OBJVIEW="Accounting Voucher View">
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Expected Success Response for Delete
```xml
<ENVELOPE>
 <HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
    <ERRORS>0</ERRORS>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
 </BODY>
</ENVELOPE>
```

---

## Payment 10: Pull All Payment Vouchers (Official TDL Collection)

Pulls all payment vouchers including ledger and nested bank allocation details using native TDL methods with `CHILDOF="$$VchTypePayment"`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Payment Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL All Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePayment</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
                </COLLECTION>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Payment 11: Pull Payment Vouchers for a Specific Period

Fetches payment vouchers within a defined date range (e.g. `01-04-2025` to `10-04-2025`) using the TDL `$$Date` period filter.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Payment Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePayment</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date &gt;= ($$Date:"01-04-2025") AND $Date &lt;= ($$Date:"10-04-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Payment 12: Pull Payment Vouchers for a Single Date

Fetches payment vouchers on a single date (e.g. `02nd April 2025` / `02-04-2025`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Payment Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Payment Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypePayment</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <NATIVEMETHOD>AllLedgerEntries.BankAllocations.*</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date = ($$Date:"02-04-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

# Part IV: Receipt Voucher Operations

---

## 1. Overview & Accounting Concepts

A **Receipt Voucher** is used to record all incoming payments and funds received by the business, whether through cash, bank transfers (NEFT / RTGS / IMPS / UPI), cheques, or other payment gateways. It captures transactions where money is collected from customers (clearing trade debtors), proceeds from cash sales, capital investments, interest/commission income, or expense refunds, ensuring accurate tracking of cash inflow.

### Financial Ledger Impact:
Each receipt transaction impacts at least two ledgers:
1. **Destination Ledger (Cash / Bank Account)**: **Debited** (`ISDEEMEDPOSITIVE="Yes"`, **negative amount** in XML e.g. `-1000000.00`) representing an increase in liquid assets.
2. **Source Ledger (Customer / Income / Credited Account)**: **Credited** (`ISDEEMEDPOSITIVE="No"`, **positive amount** in XML e.g. `1000000.00`) representing reduction in accounts receivable or recognition of earned revenue.

---

## 2. Receipt Voucher Master Tag Specifications

| Tag | Mandatory | Data Type | Permitted Values / Description |
| :--- | :--- | :--- | :--- |
| `VOUCHERTYPENAME` / `VCHTYPE` | **Yes** | String | Defines the voucher type master. Must be `Receipt` (or custom subtype under Receipt). |
| `DATE` | **Yes** | String (`YYYYMMDD`)| Primary transaction date in Tally format (e.g. `20260320`). |
| `EFFECTIVEDATE` | **Yes** | String (`YYYYMMDD`)| Date on which financial / bank impact takes effect. |
| `VCHSTATUSDATE` | **Yes** | String (`YYYYMMDD`)| Lifecycle status timestamp. |
| `VOUCHERNUMBER` | Conditional | String | Custom voucher sequence / receipt number. If omitted, Tally auto-generates sequential numbering. |
| `PARTYNAME` / `PARTYLEDGERNAME` | **Yes** | String | Primary bank / cash account or customer account. |
| `COUNTRYOFRESIDENCE` | Optional | String | Payee / Company Country (e.g. `India`). |
| `PLACEOFSUPPLY` | Optional | String | State name for GST state compliance (e.g. `Karnataka`). |
| `ALLLEDGERENTRIES.LIST` | **Yes** | Collection | Collection of all debit (Bank/Cash) and credit (Customer/Income) ledger lines. |
| `LEDGERNAME` | **Yes** | String | Exact name of the ledger master in Tally (e.g. `Bank of Baroda`, `Amar Enterprises`, `Cash`). |
| `ISDEEMEDPOSITIVE` | **Yes** | Logical / String | `Yes` for **Debit** (Cash / Bank account receiving funds), `No` for **Credit** (Customer / Income). |
| `ISPARTYLEDGER` | **Yes** | Logical / String | `Yes` for primary party / bank line, `No` for internal revenue accounts. |
| `AMOUNT` | **Yes** | Float String | Transaction amount (**Negative for Bank/Cash Debit**, **Positive for Customer/Income Credit**). |
| `BANKALLOCATIONS.LIST` | Banking | Collection | Encloses electronic transfer or cheque clearing parameters. |
| `CATEGORYALLOCATIONS.LIST` | Cost Centres | Collection | Encloses cost category and cost centre distribution. |
| `BILLALLOCATIONS.LIST` | Bills | Collection | Encloses bill reference (`Agst Ref` / `Advance` / `New Ref`). |

---

## 3. Envelope Protocols for Receipt Vouchers

Tally accepts receipt vouchers via two XML envelope formats:

1. **Direct Data Import Envelope (`Import Data`)**:
   - `<TALLYREQUEST>Import Data</TALLYREQUEST>`
   - Wrapped in `<BODY><IMPORTDATA><REQUESTDATA><TALLYMESSAGE>...`

2. **Standard API Explorer Envelope (`Import Vouchers`)**:
   - `<TALLYREQUEST>Import</TALLYREQUEST>`
   - `<TYPE>Data</TYPE>`
   - `<ID>Vouchers</ID>`
   - Wrapped in `<DESC><STATICVARIABLES><SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT><SVCURRENTCOMPANY>...</SVCURRENTCOMPANY></STATICVARIABLES></DESC><DATA><TALLYMESSAGE>...`

---

## Receipt 1: Create Receipt with Cheque / DD (Rs. 2,500 on 31-Aug-2025 from ABC Party)

Creates a Receipt Voucher on date **31st August 2025** receiving **₹2,500.00** into **Kotak Bank** from **ABC Party** with Cheque/DD instrument details and `ISCONNECTEDPAYMENT="No"`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250831</DATE>
              <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>ABC Party</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>2500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-2500.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250831</DATE>
                <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
                <TRANSACTIONTYPE>Cheque/DD</TRANSACTIONTYPE>
                <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
                <PAYMENTFAVOURING>ABC Party</PAYMENTFAVOURING>
                <INSTRUMENTNUMBER>56465787</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>ABC Party</BANKPARTYNAME>
                <ISCONNECTEDPAYMENT>No</ISCONNECTEDPAYMENT>
                <AMOUNT>-2500.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 2: Create Receipt on 01-Aug-2025 (Rs. 2,500 Cheque/DD)

Creates a Receipt Voucher on date **01st August 2025** receiving **₹2,500.00** into **Kotak Bank** from **ABC Party** with Cheque/DD banking allocations.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>ABC Party</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>2500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-2500.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250801</DATE>
                <INSTRUMENTDATE>20250801</INSTRUMENTDATE>
                <TRANSACTIONTYPE>Cheque/DD</TRANSACTIONTYPE>
                <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
                <PAYMENTFAVOURING>ABC Party</PAYMENTFAVOURING>
                <INSTRUMENTNUMBER>56465787</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>ABC Party</BANKPARTYNAME>
                <AMOUNT>-2500.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 3: Create Receipt with UPI Banking Allocations (Rs. 2,500 on 02-Aug-2025 with VPA)

Creates a Receipt Voucher on date **02nd August 2025** receiving **₹2,500.00** into **Kotak Bank** from **ABC Party** using **UPI** transfer mode with virtual payment address `767@okxis` and instrument number `5654654`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250802</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>ABC Party</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>2500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-2500.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250802</DATE>
                <INSTRUMENTDATE>20250802</INSTRUMENTDATE>
                <TRANSACTIONTYPE>UPI</TRANSACTIONTYPE>
                <VIRTUALPAYMENTADDRESS>767@okxis</VIRTUALPAYMENTADDRESS>
                <PAYMENTFAVOURING>ABC Party</PAYMENTFAVOURING>
                <INSTRUMENTNUMBER>5654654</INSTRUMENTNUMBER>
                <PAYMENTMODE>Transacted</PAYMENTMODE>
                <BANKPARTYNAME>ABC Party</BANKPARTYNAME>
                <AMOUNT>-2500.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 4: Create High-Value Cheque Receipt (Import Data Protocol)

Creates a Receipt Voucher on date **20th March 2026** receiving **₹10,00,000.00** into **Bank of Baroda** credited against **Advertising Expenses** (or Customer) with Cheque allocation (`A/c Payee`) and voucher number **32** using the `Import Data` protocol.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Import Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <IMPORTDATA>
   <REQUESTDATA>
    <TALLYMESSAGE xmlns:UDF="TallyUDF">
     <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
      <DATE>20260320</DATE>
      <EFFECTIVEDATE>20260320</EFFECTIVEDATE>
      <VCHSTATUSDATE>20260320</VCHSTATUSDATE>
      <COUNTRYOFRESIDENCE>India</COUNTRYOFRESIDENCE>
      <PLACEOFSUPPLY>Karnataka</PLACEOFSUPPLY>
      <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
      <PARTYNAME>Bank of Baroda</PARTYNAME>
      <PARTYLEDGERNAME>Bank of Baroda</PARTYLEDGERNAME>
      <VOUCHERNUMBER>32</VOUCHERNUMBER>
      <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Advertising Expenses</LEDGERNAME>
       <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>No</ISPARTYLEDGER>
       <AMOUNT>1000000.00</AMOUNT>
      </ALLLEDGERENTRIES.LIST>
      <ALLLEDGERENTRIES.LIST>
       <LEDGERNAME>Bank of Baroda</LEDGERNAME>
       <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
       <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
       <AMOUNT>-1000000.00</AMOUNT>
       <BANKALLOCATIONS.LIST>
        <DATE>20260320</DATE>
        <INSTRUMENTDATE>20260320</INSTRUMENTDATE>
        <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
        <PAYMENTFAVOURING>Advertising Expenses</PAYMENTFAVOURING>
        <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
        <BANKPARTYNAME>Advertising Expenses</BANKPARTYNAME>
        <AMOUNT>1000000.00</AMOUNT>
       </BANKALLOCATIONS.LIST>
      </ALLLEDGERENTRIES.LIST>
     </VOUCHER>
    </TALLYMESSAGE>
   </REQUESTDATA>
  </IMPORTDATA>
 </BODY>
</ENVELOPE>'
```

---

## Receipt 5: Create Customer Receipt via Bank Transfer / NEFT (Amar Enterprises)

Creates a Receipt Voucher on date **01st August 2025** receiving **₹1,180.00** into **Kotak Bank** from customer **Amar Enterprises** against invoice **Bill01SalesGST** (`Agst Ref`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Amar Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>1180.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>Bill01SalesGST</NAME>
                <BILLTYPE>Agst Ref</BILLTYPE>
                <AMOUNT>1180.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Kotak Bank</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-1180.00</AMOUNT>
               <BANKALLOCATIONS.LIST>
                <DATE>20250801</DATE>
                <INSTRUMENTDATE>20250801</INSTRUMENTDATE>
                <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
                <TRANSFERMODE>NEFT</TRANSFERMODE>
                <BANKPARTYNAME>Amar Enterprises</BANKPARTYNAME>
                <AMOUNT>-1180.00</AMOUNT>
               </BANKALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 6: Create Cash Receipt for Income with Cost Category & Cost Centre (Rs. 100 on 31-Aug-2025)

Creates a Cash Receipt Voucher on date **31st August 2025** receiving **₹100.00** in cash for **Income** distributed under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250831</DATE>
              <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYNAME>Cash</PARTYNAME>
              <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Income</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>100.00</AMOUNT>
               <CATEGORYALLOCATIONS.LIST>
                <CATEGORY>Primary Cost Category</CATEGORY>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <COSTCENTREALLOCATIONS.LIST>
                 <NAME>CostName</NAME>
                 <AMOUNT>100.00</AMOUNT>
                </COSTCENTREALLOCATIONS.LIST>
               </CATEGORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-100.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 7: Create Cash Receipt for Income on 01-Aug-2025 (Rs. 500 with Cost Centre)

Creates a Cash Receipt Voucher on date **01st August 2025** receiving **₹500.00** in cash for **Income** distributed under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <EFFECTIVEDATE>20250801</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250801</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYNAME>Cash</PARTYNAME>
              <PARTYLEDGERNAME>Cash</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Income</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>500.00</AMOUNT>
               <CATEGORYALLOCATIONS.LIST>
                <CATEGORY>Primary Cost Category</CATEGORY>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <COSTCENTREALLOCATIONS.LIST>
                 <NAME>CostName</NAME>
                 <AMOUNT>500.00</AMOUNT>
                </COSTCENTREALLOCATIONS.LIST>
               </CATEGORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 8: Create Cash Receipt from Party with Bill Allocations (ABC Party - Rs. 100 on 02-Aug-2025)

Creates a Cash Receipt Voucher on date **02nd August 2025** receiving **₹100.00** in cash from **ABC Party** with bill reference **Bill28** / `Bill30AugABC` (`New Ref`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250802</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>ABC Party</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>ABC Party</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>100.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>Bill28</NAME>
                <BILLTYPE>New Ref</BILLTYPE>
                <AMOUNT>100.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-100.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 9: Create Cash Receipt from Amar Enterprises (Rs. 500 on 02-Aug-2025)

Creates a Cash Receipt Voucher on date **02nd August 2025** collecting **₹500.00** in cash from **Amar Enterprises** with bill allocation `Bill01SalesGST` (`Agst Ref`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER VCHTYPE="Receipt" ACTION="Create" OBJVIEW="Accounting Voucher View">
              <DATE>20250802</DATE>
              <EFFECTIVEDATE>20250802</EFFECTIVEDATE>
              <VCHSTATUSDATE>20250802</VCHSTATUSDATE>
              <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
              <PARTYLEDGERNAME>Amar Enterprises</PARTYLEDGERNAME>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Amar Enterprises</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>500.00</AMOUNT>
               <BILLALLOCATIONS.LIST>
                <NAME>Bill01SalesGST</NAME>
                <BILLTYPE>Agst Ref</BILLTYPE>
                <AMOUNT>500.00</AMOUNT>
               </BILLALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-500.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 10: Alter a Receipt Voucher

Altering a Receipt Voucher in Tally requires identifying the existing record using its unique identifier (`GUID`, `REMOTEID`, or `VCHKEY`).

### Example A: Base Receipt Alteration (Change Date to `01st August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Alter" OBJVIEW="Accounting Voucher View">
              <DATE>20250801</DATE>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example B: Alter Receipt Voucher Date to `1st September 2025`
```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000089" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000120" VCHTYPE="Receipt" ACTION="Alter" OBJVIEW="Accounting Voucher View">
              <DATE>20250901</DATE>
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000088</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Example C: Alter Receipt Debit & Credit Amount Values to `₹250.00`
Alters the income credit line to `₹250.00` with cost allocations, and the cash debit line to `-₹250.00`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000088" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000118" VCHTYPE="Receipt" ACTION="Alter" OBJVIEW="Accounting Voucher View">
               <DATE>20250831</DATE>
               <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000088</GUID>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Income</LEDGERNAME>
               <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>No</ISPARTYLEDGER>
               <AMOUNT>250.00</AMOUNT>
               <CATEGORYALLOCATIONS.LIST>
                <CATEGORY>Primary Cost Category</CATEGORY>
                <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
                <COSTCENTREALLOCATIONS.LIST>
                 <NAME>CostName</NAME>
                 <AMOUNT>250.00</AMOUNT>
                </COSTCENTREALLOCATIONS.LIST>
               </CATEGORYALLOCATIONS.LIST>
              </ALLLEDGERENTRIES.LIST>
              <ALLLEDGERENTRIES.LIST>
               <LEDGERNAME>Cash</LEDGERNAME>
               <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
               <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
               <AMOUNT>-250.00</AMOUNT>
              </ALLLEDGERENTRIES.LIST>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Expected Success Response for Alter
```xml
<ENVELOPE>
 <HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <ERRORS>0</ERRORS>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
 </BODY>
</ENVELOPE>
```

---

## Receipt 11: Delete a Receipt Voucher

Deletes a specific receipt voucher by `GUID`, `REMOTEID`, or `VCHKEY`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
             <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" ACTION="Delete" OBJVIEW="Accounting Voucher View">
              <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006b</GUID>
             </VOUCHER>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
```

### Expected Success Response for Delete
```xml
<ENVELOPE>
 <HEADER><VERSION>1</VERSION><STATUS>1</STATUS></HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
    <ERRORS>0</ERRORS>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
 </BODY>
</ENVELOPE>
```

---

## Receipt 12: Pull All Receipt Vouchers (Official TDL Collection)

Pulls all receipt vouchers using native TDL methods with `CHILDOF="$$VchTypeReceipt"`.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL All Receipt Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL All Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypeReceipt</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                </COLLECTION>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 13: Pull Receipt Vouchers for a Specific Period

Fetches receipt vouchers within a defined date range (e.g. `01-07-2025` to `10-07-2025`) using the TDL `$$Date` period filter.

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Receipt Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypeReceipt</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date &gt;= ($$Date:"01-07-2025") AND $Date &lt;= ($$Date:"10-07-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## Receipt 14: Pull Receipt Vouchers for a Single Date

Fetches receipt vouchers on a single date (e.g. `01st April 2025` / `01-04-2025`).

```bash
curl --location 'http://192.168.71.129:9000/' \
--header 'Content-Type: application/xml' \
--data-raw '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Receipt Vouchers</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
              <TDLMESSAGE>
                <COLLECTION NAME="TSPL Receipt Vouchers" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                 <TYPE>Vouchers:VoucherType</TYPE>
                 <CHILDOF>$$VchTypeReceipt</CHILDOF>
                 <NATIVEMETHOD>Date, VoucherTypeName, VoucherNumber, Partyledgername</NATIVEMETHOD>
                 <FILTERS>Period Filter</FILTERS>
                </COLLECTION>
                <SYSTEM TYPE="Formulae" NAME="PeriodFilter" ISMODIFY="Yes" ISFIXED="No" ISINTERNAL="No">
                  $Date = ($$Date:"01-04-2025")
                </SYSTEM>
              </TDLMESSAGE>
            </TDL>
        </DESC>
    </BODY>
</ENVELOPE>'
```

---

## 8. Troubleshooting & Common Pitfalls

| Error Message / Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| `<RESPONSE>Unknown Request, cannot be processed</RESPONSE>` | `<VERSION>1</VERSION>` was placed inside `<HEADER>` with `<TALLYREQUEST>Import Data</TALLYREQUEST>`. | Use `<TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>Vouchers</ID>` with `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>`. |
| `<LINEERROR>Voucher date is missing</LINEERROR>` | `<DATE>`, `<EFFECTIVEDATE>`, or `<VCHSTATUSDATE>` tag is missing from the voucher body. | Ensure all 3 date tags are provided in `YYYYMMDD` format (e.g. `20250831`). |
| Inverted Debits & Credits on Receipt | Customer credited as debit, or Bank debited as credit. | In Receipt, set Bank/Cash `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (e.g. `-1000.00`), and Customer/Income `ISDEEMEDPOSITIVE="No"` with **positive** amount (`1000.00`). |
| Inverted Debits & Credits on Payment | Payee/Supplier credited instead of debited, or Bank debited instead of credited. | In Payment, set Party `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (e.g. `-200.00`), and Bank ledger `ISDEEMEDPOSITIVE="No"` with **positive** amount (`200.00`). |
| Inverted Debits & Credits on Purchase | Supplier credited as debit, or purchase expense treated as credit. | In Purchase, set Supplier Party `ISDEEMEDPOSITIVE="No"` with **positive** amount (`3120.00`), Purchase expense `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (`-3000.00`), and Input GST `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (`-60.00`). |
| `<EXCEPTIONS>1</EXCEPTIONS>` (with `<ERRORS>0</ERRORS>`) | 1. Voucher date outside active financial year.<br>2. Total debits do not balance total credits.<br>3. Bank allocations total does not match Bank ledger line amount. | 1. Verify date falls within active company FY.<br>2. Ensure sum of `-ve` debit lines equals `+ve` credit lines.<br>3. Ensure `<AMOUNT>` in `<BANKALLOCATIONS.LIST>` equals bank ledger line amount. |
| Educational Mode Rejection | Voucher date is on an unsupported day (e.g. 15th of the month). | In Tally Educational mode, dates are restricted to **1st, 2nd, or 31st** of any month. |

