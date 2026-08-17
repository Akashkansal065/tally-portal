# TallyPrime API — Complete Voucher Operations (Sales, Purchase, Payment & Receipt) & XML/cURL Integration Guide

This guide is the complete technical reference for all **Sales, Purchase, Payment, and Receipt Voucher Operations** in TallyPrime (Versions 1.0 through 5.0). It documents exact official XML envelope structures, field hierarchies, sign conventions, inventory allocation models, banking transaction allocations, cost centre distributions, tax calculations, and ready-to-run cURL/XML commands for **Create**, **Alter**, **Delete**, and **Pull** operations.

---

## Table of Contents
1. [Core Architecture & Protocol Rules](#1-core-architecture--protocol-rules)
   - [A. Envelope Selection: Import vs Import Data](#a-envelope-selection-import-vs-import-data)
   - [B. Mandatory Date Fields & Partition Keys](#b-mandatory-date-fields)
   - [C. In-Place Voucher Alteration Mechanics (VCHKEY & REMOTEID Binding)](#c-in-place-voucher-alteration-mechanics-vchkey--remoteid-binding)
   - [D. Voucher Cancellation (<ISCANCELLED>Yes</ISCANCELLED>) vs Hard Deletion (ACTION="Delete")](#d-voucher-cancellation-iscancelledyesiscancelled-vs-hard-deletion-actiondelete)
   - [E. JSONEX / JSON Protocol Specification & API Gateway Routing (Port 3000 vs Port 9000)](#e-jsonex--json-protocol-specification--api-gateway-routing-port-3000-vs-port-9000)
   - [F. Shell Variable Escaping Gotcha ($VOUCHERNUMBER in PowerShell / Bash)](#f-shell-variable-escaping-gotcha-vouchernumber-in-powershell--bash)
2. [Comparative Accounting Matrix (Sales vs Purchase vs Payment vs Receipt vs Contra)](#2-comparative-accounting-matrix-sales-vs-purchase-vs-payment-vs-receipt-vs-contra)
3. [Master Field Specifications & Banking / Cost Allocations Hierarchy](#3-master-field-specifications--banking--cost-allocations-hierarchy)
4. [Part I: Sales Voucher Operations](#4-part-i-sales-voucher-operations)
5. [Part II: Purchase Voucher Operations](#5-part-ii-purchase-voucher-operations)
6. [Part III: Payment Voucher Operations](#6-part-iii-payment-voucher-operations)
7. [Part IV: Receipt Voucher Operations](#7-part-iv-receipt-voucher-operations)
8. [Part V: Contra Voucher Operations (Cash Deposits, Cash Withdrawals & Bank Transfers)](#8-part-v-contra-voucher-operations)
   - [Contra 1: Cash Deposit into Bank with Cash Denomination & Bank Allocations](#contra-1-cash-deposit-into-bank)
   - [Contra 2: Cash Withdrawal from Bank with Cheque Banking Allocations](#contra-2-cash-withdrawal-from-bank)
   - [Contra 3: Bank-to-Bank Fund Transfer (NEFT / RTGS)](#contra-3-bank-to-bank-fund-transfer)
   - [Contra 4: Alter a Contra Voucher](#contra-4-alter-a-contra-voucher)
   - [Contra 5: Delete a Contra Voucher](#contra-5-delete-a-contra-voucher)
   - [Contra 6: Pull All Contra Vouchers / Pull for Specific Period](#contra-6-pull-all-contra-vouchers)
9. [Part VI: TallyPrime F12 Voucher Configuration Specifications & Field Matrix](#9-part-vi-tallyprime-f12-voucher-configuration-specifications)
   - [A. Comparative F12 Configuration Matrix across Voucher Types](#a-comparative-f12-configuration-matrix-across-voucher-types)
   - [B. Detailed Technical Specifications for Each Configuration Parameter](#b-detailed-technical-specifications-for-each-configuration-parameter)
   - [C. XML Data Flow & ERP Synchronization Mechanism](#c-xml-data-flow--erp-synchronization-mechanism)
10. [Part VII: TallyPrime Official JSON / JSONEX API Specification](#10-part-vii-tallyprime-official-json--jsonex-api-specification)
    - [JSON 1: Export / Pull All Sales Vouchers](#json-1-export--pull-all-sales-vouchers)
    - [JSON 2: Create Sales Item Invoice Voucher](#json-2-create-sales-item-invoice-voucher)
    - [JSON 3: Alter Sales Voucher In-Place (Using VCHKEY)](#json-3-alter-sales-voucher-in-place-using-vchkey)
    - [JSON 4: Cancel Voucher In-Place ("iscancelled": true)](#json-4-cancel-voucher-in-place-iscancelled-true)
    - [JSON 5: Hard Delete Voucher ("Action": "Delete")](#json-5-hard-delete-voucher-action-delete)
11. [Troubleshooting & Common Pitfalls](#11-troubleshooting--common-pitfalls)

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

### C. In-Place Voucher Alteration Mechanics (`VCHKEY` & `REMOTEID` Binding)
In TallyPrime, vouchers configured with **Automatic Numbering** (`Numbering Method: Automatic` or `Auto Retain`) generate a **new sequence number** if the imported XML/JSON does not provide Tally's internal binary pointer.

To achieve true **in-place voucher alteration** without incrementing the voucher counter:
1. **`REMOTEID="{guid}"`**: The exact Tally GUID assigned during creation.
2. **`VCHKEY="{company_guid}-{date_hex}:{master_id_hex}"`**: Tally's internal binary voucher key (e.g. `f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000080`), obtained from collection export.
3. **`ACTION="Alter"`** / `"Action": "Alter"`.
4. **`<GUID>{guid}</GUID>`**: Matching GUID inside the `<VOUCHER>` body.

```xml
<VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c3" 
         VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000080" 
         VCHTYPE="Purchase" 
         ACTION="Alter" 
         OBJVIEW="Invoice Voucher View">
    <DATE>20260301</DATE>
    <EFFECTIVEDATE>20260301</EFFECTIVEDATE>
    <VCHSTATUSDATE>20260301</VCHSTATUSDATE>
    <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
    <VOUCHERNUMBER>18</VOUCHERNUMBER>
    <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c3</GUID>
    ...
</VOUCHER>
```

---

### D. Voucher Cancellation (`<ISCANCELLED>Yes</ISCANCELLED>`) vs Hard Deletion (`ACTION="Delete"`)

| Feature | 🚫 **Cancellation (`<ISCANCELLED>Yes</ISCANCELLED>`)** | 🗑️ **Hard Deletion (`ACTION="Delete"`)** |
| :--- | :--- | :--- |
| **Operation Type** | `ACTION="Alter"` with `<ISCANCELLED>Yes</ISCANCELLED>` | `ACTION="Delete"` / `"Action": "Delete"` |
| **Audit Sequence** | **Preserved intact** (no missing voucher numbers) | **Leaves gaps** in auto-numbered sequences |
| **Financial Balances** | **Zeroes out debits & credits** | Record removed |
| **Inventory / Stock** | **Reverses all stock movements immediately** | **Reverses all stock movements immediately** |
| **Dependency Locks** | Works without triggering dependency exceptions | Rejects if open in UI or has locked references |
| **Day Book UI** | Displayed as **`(Cancelled)`** with ₹0.00 | Removed from list |

#### 1. Official Cancellation XML Payload:
```xml
<ENVELOPE>
    <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>Vouchers</ID></HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8" 
                         VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0" 
                         VCHTYPE="Sales" 
                         ACTION="Alter" 
                         OBJVIEW="Invoice Voucher View">
                    <DATE>20250831</DATE>
                    <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
                    <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
                    <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
                    <VOUCHERNUMBER>54</VOUCHERNUMBER>
                    <ISCANCELLED>Yes</ISCANCELLED>
                    <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8</GUID>
                </VOUCHER>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

#### 2. Official Hard Delete XML Payload:
```xml
<ENVELOPE>
    <HEADER><VERSION>1</VERSION><TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>Vouchers</ID></HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8" 
                         VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0" 
                         VCHTYPE="Sales" 
                         ACTION="Delete" 
                         OBJVIEW="Invoice Voucher View">
                    <DATE>20250831</DATE>
                    <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8</GUID>
                </VOUCHER>
            </TALLYMESSAGE>
        </DESC>
    </BODY>
</ENVELOPE>
```

---

### E. JSONEX / JSON Protocol Specification & API Gateway Routing (Port 3000 vs Port 9000)

1. **Port 3000 (`http://127.0.0.1:3000/`)**:
   - **Tally API Gateway / Explorer Router**: Provided by Tally Developer Tools.
   - Reads HTTP headers (`id: Vouchers`, `tallyrequest: import`, `type: data`, `x-tally-port: 9000`) and translates JSON to internal TDL binary.
2. **Port 9000 (`http://127.0.0.1:9000/`)**:
   - **Raw Native Tally Engine**: Expects standard XML `<ENVELOPE>` or native JSONEX.
3. **Case-Sensitivity in JSONEX**:
   - In JSONEX format, the metadata attribute MUST be capitalized: **`"Action": "Delete"`** or **`"Action": "Alter"`** (capital **`A`**).
   - Mandatory date partition fields (`date`, `effectivedate`, `vchstatusdate`, `vouchernumber`, `vouchertypename`) must be included in the body.

---

### F. Shell Variable Escaping Gotcha (`$VOUCHERNUMBER` in PowerShell / Bash)
When sending TDL Collection requests containing formulas from PowerShell or Bash:
* **PowerShell Gotcha**: PowerShell automatically evaluates `$VOUCHERNUMBER` as a shell variable. Because it is unset, `$VOUCHERNUMBER = "54"` is converted to `= "54"`, causing Tally to show the GUI error dialog: `Bad formula! '= "54"'`.
* **Fix in PowerShell**: Escape the dollar sign with a backtick:
  ```powershell
  `$VOUCHERNUMBER = "54"
  ``$$IsSales:`$VOUCHERTYPENAME
  ```
* **Fix in cURL / Postman**: Use single quotes in bash (`--data-raw '...'`) or execute via Postman where variable interpolation does not occur.

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
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>193</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>86</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>15</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>16</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>22</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>50</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>50</VOUCHERNUMBERSERIES>
    <VOUCHER>38</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>193</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Sales 2: Create Sales Voucher for 0% Tax / Exempt Item

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>194</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>89</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>17</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>17</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>23</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>51</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>51</VOUCHERNUMBERSERIES>
    <VOUCHER>39</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>194</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Sales 3: Create Sales Voucher with Multiple Items, Batches & Godowns

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <LINEERROR>Godown &apos;Warehouse A&apos; does not exist!</LINEERROR>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>95</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>18</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>19</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>23</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>52</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>52</VOUCHERNUMBERSERIES>
    <VOUCHER>39</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>307</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Sales 4: Alter a Sales Voucher

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>95</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>18</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>19</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>23</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>53</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>53</VOUCHERNUMBERSERIES>
    <VOUCHER>39</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>308</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Sales 5: Delete a Sales Voucher

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>95</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>18</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>19</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>23</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>53</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>53</VOUCHERNUMBERSERIES>
    <VOUCHER>39</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Sales 6: Pull All Sales Vouchers / Pull for Period

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>95</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>18</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>19</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>23</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>53</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>53</VOUCHERNUMBERSERIES>
    <VOUCHER>39</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISCMPDEPTYPE="Yes" CMPLOCUS="4" CMPDEPTYPE="64">
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000005" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2d1:00000008" VCHTYPE="Sales" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250501</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000005</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>1</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20250501</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 6</ALTERID>
     <MASTERID TYPE="Number"> 5</MASTERID>
     <VOUCHERKEY TYPE="Number">196610717909000</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">1</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-250000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-250000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-250000.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">250000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000022" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2f0:00000010" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250601</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000022</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>8</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 66</ALTERID>
     <MASTERID TYPE="Number"> 34</MASTERID>
     <VOUCHERKEY TYPE="Number">196743861895184</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">29</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">213.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Batch1</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">213.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Batch1</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">21300.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000023" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2f0:00000018" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250601</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000023</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>9</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 67</ALTERID>
     <MASTERID TYPE="Number"> 35</MASTERID>
     <VOUCHERKEY TYPE="Number">196743861895192</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">33</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">213.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Batch1</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">213.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Batch1</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">21300.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000a" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2f1:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250602</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000a</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Jagdish Enterprise</PARTYLEDGERNAME>
     <VOUCHERNUMBER>2</VOUCHERNUMBER>
     <REFERENCE TYPE="String">2</REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 70</ALTERID>
     <MASTERID TYPE="Number"> 10</MASTERID>
     <VOUCHERKEY TYPE="Number">196748156862472</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">5</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-5856000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">180000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">2700000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">2700000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">180000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">2700000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Hp Pavilion 14 Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">125000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1875000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1875000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">125000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1875000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Hp Smart Tank 670 Printers</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">30000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">450000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">450000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">30000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">450000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Epson Eco Tank L 3252 Printers</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">23000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">345000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">345000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">23000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">345000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Samsung 32 inch Curved Monitor</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">21500.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">258000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">258000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">21500.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">258000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">LG 32MR50C Curved Monitor</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">19000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">228000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">228000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">19000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">228000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Jagdish Enterprise</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-5856000.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-5856000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Jagdish Enterprise</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-5856000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-5856000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">5856000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">180000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">2700000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">2700000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">180000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Hp Pavilion 14 Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">125000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1875000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1875000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">125000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Hp Smart Tank 670 Printers</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">30000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">450000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">450000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">30000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Epson Eco Tank L 3252 Printers</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">23000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">345000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">345000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 15 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 15 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">23000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Samsung 32 inch Curved Monitor</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">21500.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">258000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">258000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">21500.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">LG 32MR50C Curved Monitor</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">19000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">228000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">228000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 12 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 12 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">19000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000024" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2f1:00000020" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250602</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000024</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>6</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 68</ALTERID>
     <MASTERID TYPE="Number"> 36</MASTERID>
     <VOUCHERKEY TYPE="Number">196748156862496</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">21</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">213.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Batch1</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Abc Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">213.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Batch1</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">21300.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <UDF:_UDF_788538143.LIST DESC="" ISLIST="YES" TYPE="String" INDEX="8990">
      <UDF:_UDF_788538143 DESC="">SM Travels</UDF:_UDF_788538143>
     </UDF:_UDF_788538143.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000025" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2f1:00000028" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250602</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000025</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">XYZ Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>7</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 69</ALTERID>
     <MASTERID TYPE="Number"> 37</MASTERID>
     <VOUCHERKEY TYPE="Number">196748156862504</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">25</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">213.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Batch1</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">XYZ Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">XYZ Party</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-21300.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">21300.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Item1</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">213.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">21300.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
       <CATEGORYALLOCATIONS.LIST>       </CATEGORYALLOCATIONS.LIST>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Batch1</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">21300.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 100 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 100 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">213.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <UDF:_UDF_788538143.LIST DESC="" ISLIST="YES" TYPE="String" INDEX="8990">
      <UDF:_UDF_788538143 DESC="">SM Travels</UDF:_UDF_788538143>
     </UDF:_UDF_788538143.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000f" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b30f:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250702</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000f</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">ANS Traders</PARTYLEDGERNAME>
     <VOUCHERNUMBER>3</VOUCHERNUMBER>
     <REFERENCE TYPE="String">3</REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 16</ALTERID>
     <MASTERID TYPE="Number"> 15</MASTERID>
     <VOUCHERKEY TYPE="Number">196877005881352</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">9</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-465000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Hp Pavilion 14 Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">125000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">375000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">375000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">125000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">375000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Hp Smart Tank 670 Printers</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">30000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">90000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">90000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">30000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">90000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">ANS Traders</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-465000.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-100000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-365000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">ANS Traders</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-465000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-100000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-365000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">465000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Hp Pavilion 14 Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">125000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">375000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">375000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">125000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Hp Smart Tank 670 Printers</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">30000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">90000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">90000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 3 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 3 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">30000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000048" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000092</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>34</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 307</ALTERID>
     <MASTERID TYPE="Number"> 146</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900296</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">133</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ab" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000060" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ab</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>46</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 339</ALTERID>
     <MASTERID TYPE="Number"> 171</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900320</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">181</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ac" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000068" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ac</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>47</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 340</ALTERID>
     <MASTERID TYPE="Number"> 172</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900328</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">185</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ad" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000070" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ad</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>48</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 341</ALTERID>
     <MASTERID TYPE="Number"> 173</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900336</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">189</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ae" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000078" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ae</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>49</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 342</ALTERID>
     <MASTERID TYPE="Number"> 174</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900344</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">193</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T002</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T002</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000af" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000080" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000af</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>50</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 343</ALTERID>
     <MASTERID TYPE="Number"> 175</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900352</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">197</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c1" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000b0" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c1</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>51</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 365</ALTERID>
     <MASTERID TYPE="Number"> 193</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900400</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">201</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T002</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T002</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c2" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000b8" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c2</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>52</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 366</ALTERID>
     <MASTERID TYPE="Number"> 194</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900408</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">205</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000096" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000096</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>38</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 311</ALTERID>
     <MASTERID TYPE="Number"> 150</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867528</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">149</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Decaf Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000089" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000f8" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000089</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>27</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 297</ALTERID>
     <MASTERID TYPE="Number"> 137</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919352</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">105</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008a" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000100" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008a</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>28</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 298</ALTERID>
     <MASTERID TYPE="Number"> 138</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919360</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">109</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008d" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000118" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008d</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>29</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 301</ALTERID>
     <MASTERID TYPE="Number"> 141</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919384</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">113</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008e" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000120" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008e</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>30</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 302</ALTERID>
     <MASTERID TYPE="Number"> 142</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919392</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">117</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000128" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000091</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>33</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 306</ALTERID>
     <MASTERID TYPE="Number"> 145</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919400</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">129</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-40.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Amar Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-40.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">40.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Coffee Powder</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">40.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">40.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000093" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b3e5:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260201</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000093</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Chanda Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>35</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 308</ALTERID>
     <MASTERID TYPE="Number"> 147</MASTERID>
     <VOUCHERKEY TYPE="Number">197796128882696</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">137</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">75.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">3000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">3000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">75.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">3000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b3e6:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260202</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000095</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Chanda Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>37</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 310</ALTERID>
     <MASTERID TYPE="Number"> 149</MASTERID>
     <VOUCHERKEY TYPE="Number">197800423849992</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">145</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">75.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">3000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-3150.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">3000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">75.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">3000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">3000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 40 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 40 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">75.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008f" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000008" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008f</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Chanda Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>31</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 303</ALTERID>
     <MASTERID TYPE="Number"> 143</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387966984</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">121</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">75.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">75.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1500.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000090" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000010" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000090</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Chanda Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>32</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 304</ALTERID>
     <MASTERID TYPE="Number"> 144</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387966992</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">125</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">75.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">75.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1500.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000094" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000018" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000094</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Chanda Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>36</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 309</ALTERID>
     <MASTERID TYPE="Number"> 148</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967000</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">141</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">75.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Chanda Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1575.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">GST Coffee</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">75.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1500.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 20 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 20 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">75.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">37.50</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a1" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000030" VCHTYPE="Sales" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a1</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>39</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 329</ALTERID>
     <MASTERID TYPE="Number"> 161</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967024</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">153</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-1000.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a5" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000050" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a5</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>40</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 333</ALTERID>
     <MASTERID TYPE="Number"> 165</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967056</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">157</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a6" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000058" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a6</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>41</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 334</ALTERID>
     <MASTERID TYPE="Number"> 166</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967064</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">161</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">T001</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a7" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000060" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a7</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>42</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 335</ALTERID>
     <MASTERID TYPE="Number"> 167</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967072</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">165</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">500.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 2 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 2 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 2 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 2 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">500.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-1000.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-1000.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">500.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 2 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 2 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 2 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 2 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">500.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a8" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000068" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a8</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>43</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 336</ALTERID>
     <MASTERID TYPE="Number"> 168</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967080</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">169</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1180.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">CGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">SGST</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">90.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a9" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000070" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a9</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>44</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 337</ALTERID>
     <MASTERID TYPE="Number"> 169</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967088</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">173</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-2000.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">2000.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">2000.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">2000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">2000.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">2000.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-2000.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-2000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-2000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-2000.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">2000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">2000.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">2000.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">2000.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">2000.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000aa" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000078" VCHTYPE="Sales" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000aa</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>45</VOUCHERNUMBER>
     <REFERENCE TYPE="String"></REFERENCE>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <ALTERID TYPE="Number"> 338</ALTERID>
     <MASTERID TYPE="Number"> 170</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967096</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">177</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <AMOUNT TYPE="Amount">-1500.00</AMOUNT>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLINVENTORYENTRIES.LIST>
      <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
      <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <RATE TYPE="Rate">1500.00/nos</RATE>
      <DISCOUNT TYPE="Number">0</DISCOUNT>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
      <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
      <BATCHALLOCATIONS.LIST>
       <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
       <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
       <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
       <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHRATE TYPE="Rate">1500.00/nos</BATCHRATE>
      </BATCHALLOCATIONS.LIST>
      <ACCOUNTINGALLOCATIONS.LIST>
       <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <BILLALLOCATIONS.LIST>       </BILLALLOCATIONS.LIST>
       <TAXOBJECTALLOCATIONS.LIST>       </TAXOBJECTALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </ACCOUNTINGALLOCATIONS.LIST>
     </ALLINVENTORYENTRIES.LIST>
     <LEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1500.00</AMOUNT>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1500.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </LEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-1500.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">GST Sales</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <INVENTORYALLOCATIONS.LIST>
       <STOCKITEMNAME TYPE="String">Apple MacBook Pro Laptop</STOCKITEMNAME>
       <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
       <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
       <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
       <RATE TYPE="Rate">1500.00/nos</RATE>
       <DISCOUNT TYPE="Number">0</DISCOUNT>
       <AMOUNT TYPE="Amount">1500.00</AMOUNT>
       <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
       <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
       <BATCHALLOCATIONS.LIST>
        <BATCHNAME TYPE="String">Primary Batch</BATCHNAME>
        <INDENTNO TYPE="String">&#4; Not Applicable</INDENTNO>
        <ORDERNO TYPE="String">&#4; Not Applicable</ORDERNO>
        <TRACKINGNUMBER TYPE="String">&#4; Not Applicable</TRACKINGNUMBER>
        <ADDLAMOUNT TYPE="Amount"></ADDLAMOUNT>
        <BATCHDISCOUNT TYPE="Number">0</BATCHDISCOUNT>
        <AMOUNT TYPE="Amount">1500.00</AMOUNT>
        <ACTUALQTY TYPE="Quantity"> 1 nos</ACTUALQTY>
        <BILLEDQTY TYPE="Quantity"> 1 nos</BILLEDQTY>
        <BATCHRATE TYPE="Rate">1500.00/nos</BATCHRATE>
       </BATCHALLOCATIONS.LIST>
       <COSTTRACKALLOCATIONS.LIST>       </COSTTRACKALLOCATIONS.LIST>
      </INVENTORYALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```

---

# Part II: Purchase Voucher Operations

---

## Purchase 1: Create Standard Item Purchase

Creates an Item Purchase for **Computer US** (20 nos @ ₹10,000 = ₹2,00,000) on date **01st March 2026** from **International Party** with bill reference **12**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>195</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>98</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>19</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>20</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>24</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>54</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>54</VOUCHERNUMBERSERIES>
    <VOUCHER>40</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>195</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Purchase 2: Create Purchase Voucher with Custom Date

Creates a Purchase voucher for **Computer US** (10 nos @ ₹10,000 = ₹1,00,000) on date **01st February 2026** with bill number **Bill28Pur1**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>196</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>101</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>20</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>21</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>25</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>55</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>55</VOUCHERNUMBERSERIES>
    <VOUCHER>41</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>196</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Purchase 3: Create Domestic Purchase with GST

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>197</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>106</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>22</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>24</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>26</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>56</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>56</VOUCHERNUMBERSERIES>
    <VOUCHER>43</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>197</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Purchase 4: Create Domestic Purchase with GST on 01-Aug-2025

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>198</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>111</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>24</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>27</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>27</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>57</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>57</VOUCHERNUMBERSERIES>
    <VOUCHER>45</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>198</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Purchase 5: Alter a Purchase Voucher

### Example A: Base Purchase Alteration (Change Date to `02nd August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>111</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>24</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>27</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>27</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>58</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>58</VOUCHERNUMBERSERIES>
    <VOUCHER>45</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>313</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example B: Alter Purchase Voucher Date to `1st March 2026`
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>111</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>24</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>27</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>27</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>60</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>60</VOUCHERNUMBERSERIES>
    <VOUCHER>45</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example C: Alter Item Quantity to `15 nos` with Full Amount Recalculation
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>313</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>114</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>25</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>28</STOCKITEM>
    <VOUCHERTYPE>3</VOUCHERTYPE>
    <CURRENCY>28</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>62</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>62</VOUCHERNUMBERSERIES>
    <VOUCHER>46</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Purchase 6: Delete a Purchase Voucher

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
    <LASTVCHID>313</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>117</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>29</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>63</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>63</VOUCHERNUMBERSERIES>
    <VOUCHER>48</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Purchase 7: Pull All Purchase Vouchers (Official TDL Collection)

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>117</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>29</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>63</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>63</VOUCHERNUMBERSERIES>
    <VOUCHER>48</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000004" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000010" VCHTYPE="Purchase" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250402</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000004</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>1</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 4</MASTERID>
     <VOUCHERKEY TYPE="Number">196486163857424</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">1</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000d" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b30e:00000008" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250701</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000d</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Raman Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>3</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 13</MASTERID>
     <VOUCHERKEY TYPE="Number">196872710914056</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">9</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000011" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b30e:00000018" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250701</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000011</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Vishal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>4</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 17</MASTERID>
     <VOUCHERKEY TYPE="Number">196872710914072</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">13</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009a" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000050" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009a</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Mondal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>15</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 154</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900304</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">57</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009c" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000058" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009c</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Mondal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>17</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 156</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900312</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">65</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c6" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000c0" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c6</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Mondal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>21</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 198</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900416</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">81</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000073" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000e8" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000073</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Jagdish Enterprise</PARTYLEDGERNAME>
     <VOUCHERNUMBER>8</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 115</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919336</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">29</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34c:00000010" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250901</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000009b</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Mondal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>16</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 155</MASTERID>
     <VOUCHERKEY TYPE="Number">197138998886416</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">61</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c5" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34c:00000018" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20250901</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c5</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Mondal Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>20</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 197</MASTERID>
     <VOUCHERKEY TYPE="Number">197138998886424</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">77</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000098" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b3e5:00000010" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260201</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000098</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>13</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 152</MASTERID>
     <VOUCHERKEY TYPE="Number">197796128882704</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">49</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000099" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b3e5:00000018" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260201</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000099</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>14</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 153</MASTERID>
     <VOUCHERKEY TYPE="Number">197796128882712</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">53</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c4" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b3e5:00000020" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260201</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c4</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>19</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 196</MASTERID>
     <VOUCHERKEY TYPE="Number">197796128882720</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">73</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000097" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000020" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000097</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>12</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 151</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967008</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">45</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c3" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000080" VCHTYPE="Purchase" OBJVIEW="Invoice Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c3</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">International Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>18</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Invoice Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>Yes</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 195</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967104</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">69</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Purchase 8: Pull Purchase Vouchers for a Specific Period

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>117</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>29</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>63</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>63</VOUCHERNUMBERSERIES>
    <VOUCHER>48</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Purchase 9: Pull Purchase Vouchers for a Single Date

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>117</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>29</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>63</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>63</VOUCHERNUMBERSERIES>
    <VOUCHER>48</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000004" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000010" VCHTYPE="Purchase" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250402</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000004</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>1</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 4</MASTERID>
     <VOUCHERKEY TYPE="Number">196486163857424</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">1</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

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
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<RESPONSE>Unknown Request, cannot be processed</RESPONSE>
```---

## Payment 2: Create Payment with Inter Bank Transfer / NEFT

Creates a Payment Voucher on date **31st August 2025** for party **Akshaya Enterprises** of amount **₹200.00** paid via **Kotak Bank** with full NEFT electronic banking allocations.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>200</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>121</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>30</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>64</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>64</VOUCHERNUMBERSERIES>
    <VOUCHER>50</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>200</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Payment 3: Create Payment with Custom Amount

Creates a Payment Voucher on date **01st August 2025** for party **Akshaya Enterprises** of amount **₹900.00** paid via **Kotak Bank** with NEFT.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>201</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>125</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>31</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>65</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>65</VOUCHERNUMBERSERIES>
    <VOUCHER>52</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>201</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Payment 4: Create Payment with Cheque Banking Allocations

Creates a Payment Voucher on date **02nd August 2025** for party **Akshaya Enterprises** of amount **₹200.00** paid via **Kotak Bank** with Cheque allocations and `A/c Payee` crossing.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>202</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>129</LEDGER>
    <COSTCATEGORY>9</COSTCATEGORY>
    <COSTCENTRE>9</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>32</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>66</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>66</VOUCHERNUMBERSERIES>
    <VOUCHER>54</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>202</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```

---

## Payment 5: Create Cash Payment for Expenses with Cost Category & Cost Centre

Creates a Cash Payment Voucher on date **31st August 2025** for **Sundry Expenses** of amount **₹100.00** with cost allocations under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>203</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>132</LEDGER>
    <COSTCATEGORY>10</COSTCATEGORY>
    <COSTCENTRE>10</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>33</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>67</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>67</VOUCHERNUMBERSERIES>
    <VOUCHER>56</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>203</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Payment 6: Create Cash Payment for Expenses on 01-Aug-2025

Creates a Cash Payment Voucher on date **01st August 2025** for **Sundry Expenses** of amount **₹500.00** with cost allocations under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>204</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>135</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>34</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>68</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>68</VOUCHERNUMBERSERIES>
    <VOUCHER>58</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>204</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Payment 7: Create Cash Payment to Party with Bill Allocations

Creates a Cash Payment Voucher on date **02nd August 2025** paying supplier **Akshaya Enterprises** amount **₹500.00** in cash with bill reference **Bill30AugAE** (`New Ref`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>205</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>138</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>35</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>69</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>69</VOUCHERNUMBERSERIES>
    <VOUCHER>59</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>205</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Payment 8: Alter a Payment Voucher

Altering a Payment Voucher in Tally requires identifying the existing record using its unique identifier (`GUID`, `REMOTEID`, or `VCHKEY`).

### Example A: Base Payment Alteration (Change Date to `01st August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>291</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>138</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>36</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>70</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>70</VOUCHERNUMBERSERIES>
    <VOUCHER>60</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example B: Alter Payment Voucher Date to `1st September 2025`
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>291</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>138</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>37</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>72</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>73</VOUCHERNUMBERSERIES>
    <VOUCHER>61</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example C: Alter Payment Debit & Credit Amount Values to `₹250.00`
Alters both the party debit ledger and the cash credit ledger to `₹250.00`, with updated bill allocation `Bill30AugAE`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>291</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>141</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>4</VOUCHERTYPE>
    <CURRENCY>38</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>74</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>75</VOUCHERNUMBERSERIES>
    <VOUCHER>62</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Payment 9: Delete a Payment Voucher

Deletes a specific payment voucher by `GUID`, `REMOTEID`, or `VCHKEY`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
    <LASTVCHID>291</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>144</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>39</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>75</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>76</VOUCHERNUMBERSERIES>
    <VOUCHER>64</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Payment 10: Pull All Payment Vouchers (Official TDL Collection)

Pulls all payment vouchers including ledger and nested bank allocation details using native TDL methods with `CHILDOF="$$VchTypePayment"`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>144</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>39</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>75</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>76</VOUCHERNUMBERSERIES>
    <VOUCHER>64</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000001d" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000010" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250401</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000001d</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Vishnu Traders</PARTYLEDGERNAME>
     <VOUCHERNUMBER>10</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20250401</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 29</MASTERID>
     <VOUCHERKEY TYPE="Number">196481868890128</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">37</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Vishnu Traders</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-10000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-10000.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">10000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000003" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250402</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000003</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">HDFC BANK A/c</PARTYLEDGERNAME>
     <VOUCHERNUMBER>2</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 3</MASTERID>
     <VOUCHERKEY TYPE="Number">196486163857416</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">5</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Office Rent</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">HDFC BANK A/c</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250402</DATE>
       <INSTRUMENTDATE>20250402</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>403969a1-2229-437a-bc0b-f61ad80e9861</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE/>
       <BANKNAME/>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER/>
       <PAYMENTFAVOURING>Office Rent</PAYMENTFAVOURING>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
       <TRANSFERMODE/>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER/>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER>5GG6JKFszBXyHqnr</UNIQUEREFERENCENUMBER>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Office Rent</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>50000.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000006" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2d2:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250502</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000006</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>3</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 6</MASTERID>
     <VOUCHERKEY TYPE="Number">196615012876296</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">9</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Printing &amp; Stationery</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">1000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000010" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32c:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250731</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000010</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">HDFC BANK A/c</PARTYLEDGERNAME>
     <VOUCHERNUMBER>4</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 16</MASTERID>
     <VOUCHERKEY TYPE="Number">197001559932936</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">13</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Office Rent</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">HDFC BANK A/c</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250731</DATE>
       <INSTRUMENTDATE>20250731</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>0589d570-077c-4ad2-8d9a-3dc9fa60f148</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE/>
       <BANKNAME/>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER/>
       <PAYMENTFAVOURING>Office Rent</PAYMENTFAVOURING>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
       <TRANSFERMODE/>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER/>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER>5GIuaE7WzBXyHqnr</UNIQUEREFERENCENUMBER>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Office Rent</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>50000.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b1" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000088" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b1</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>41</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 177</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900360</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">161</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-900.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-900.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">900.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250801</DATE>
       <INSTRUMENTDATE>20250801</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>6f69a740-855f-41ce-9b80-8945fed06472</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000432</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>6757657567</ACCOUNTNUMBER>
       <PAYMENTFAVOURING/>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER/>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>900.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b4" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000090" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b4</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>44</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 180</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900368</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">173</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sundry Expenses</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c9" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000c8" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c9</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>51</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 201</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900424</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">201</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-900.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-900.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">900.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250801</DATE>
       <INSTRUMENTDATE/>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>e8374159-01a0-4a80-8371-e0f719321d0b</NAME>
       <EMAIL>a@gmail.com</EMAIL>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000431</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>900.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cc" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000d0" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cc</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>54</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 204</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900432</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">213</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sundry Expenses</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b2" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000010" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b2</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>42</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 178</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867536</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">165</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250802</DATE>
       <INSTRUMENTDATE>20250802</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>ba901016-5ee3-40df-b0f5-43c406fa8d76</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE/>
       <BANKNAME/>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER/>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
       <TRANSFERMODE/>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER>7656876878</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b5" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000018" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b5</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>45</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 181</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867544</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">177</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ca" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000038" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ca</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>52</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 202</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867576</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">205</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250802</DATE>
       <INSTRUMENTDATE>20250802</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>b263803f-6f3e-43af-95b9-fcb9867bccb8</NAME>
       <EMAIL>a@gmail.com</EMAIL>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE/>
       <BANKNAME/>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER/>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
       <TRANSFERMODE/>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER>7656876878</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cd" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000040" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cd</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>55</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 205</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867584</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">217</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008b" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000108" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008b</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>34</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 139</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919368</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">133</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250831</DATE>
       <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>74cd97f4-344e-4ad7-a65e-e363cf33e135</NAME>
       <EMAIL>a@gmail.com</EMAIL>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000431</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID>10</BANKID>
       <INSTRUMENTNUMBER>100</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008c" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000110" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000008c</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>35</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 140</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919376</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">137</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250831</DATE>
       <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>df0bea25-4e35-49c1-9d75-f3d508f0d40e</NAME>
       <EMAIL>a@gmail.com</EMAIL>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000431</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b0" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000130" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b0</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>40</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 176</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919408</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">157</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250831</DATE>
       <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>37af8506-c0e8-49d8-969c-190d95f2e913</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000432</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>6757657567</ACCOUNTNUMBER>
       <PAYMENTFAVOURING/>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER/>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b3" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000138" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b3</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>43</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 179</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919416</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">169</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sundry Expenses</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b6" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000148" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b6</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>47</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 182</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919432</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">185</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sundry Expenses</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000012f" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000160" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000012f</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>48</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 303</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919456</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">189</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Income</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c8" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000170" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c8</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>50</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 200</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919472</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">197</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <AMOUNT TYPE="Amount">-200.00</AMOUNT>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Kotak Bank</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">200.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250831</DATE>
       <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>072a8945-8de6-4624-ba22-57d02b813b33</NAME>
       <EMAIL>a@gmail.com</EMAIL>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE>KKBK0000431</IFSCODE>
       <BANKNAME>Kotak Mahindra Bank (India)</BANKNAME>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER>4891289138912</ACCOUNTNUMBER>
       <PAYMENTFAVOURING>Akshaya Enterprises</PAYMENTFAVOURING>
       <TRANSACTIONNAME>Primary</TRANSACTIONNAME>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT/>
       <TRANSFERMODE>NEFT</TRANSFERMODE>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER>6556876878</INSTRUMENTNUMBER>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER/>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Akshaya Enterprises</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>200.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cb" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000178" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cb</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>53</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 203</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919480</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">209</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Sundry Expenses</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <CATEGORYALLOCATIONS.LIST>      </CATEGORYALLOCATIONS.LIST>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">100.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a0" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000028" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a0</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>36</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 160</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967016</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">141</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-500.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">500.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a2" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000038" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a2</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>37</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 162</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967032</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">145</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-50.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-50.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">50.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a3" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000040" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a3</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>38</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 163</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967040</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">149</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-250.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a4" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b401:00000048" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20260301</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000a4</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Akshaya Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>39</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <EFFECTIVEDATE TYPE="Date">20260301</EFFECTIVEDATE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 164</MASTERID>
     <VOUCHERKEY TYPE="Number">197916387967048</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">153</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Akshaya Enterprises</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>
       <YEAREND/>
       <NAME/>
       <BILLCREDITPERIOD/>
       <TDSDEDUCTEESECTIONNUMBER/>
       <TDSLEDGERNC/>
       <SERVICETAXLEDGER/>
       <BILLTYPE TYPE="String">On Account</BILLTYPE>
       <SUMNAME/>
       <TDSDEDUCTEEISSPECIALRATE>No</TDSDEDUCTEEISSPECIALRATE>
       <TDSDEDUCTEESPECIALRATE>0</TDSDEDUCTEESPECIALRATE>
       <AMOUNT>-250.00</AMOUNT>
       <INTERESTCOLLECTION.LIST>       </INTERESTCOLLECTION.LIST>
       <STBILLCATEGORIES.LIST>       </STBILLCATEGORIES.LIST>
      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Cash</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">250.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Payment 11: Pull Payment Vouchers for a Specific Period

Fetches payment vouchers within a defined date range (e.g. `01-04-2025` to `10-04-2025`) using the TDL `$$Date` period filter.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>144</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>39</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>75</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>76</VOUCHERNUMBERSERIES>
    <VOUCHER>64</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Payment 12: Pull Payment Vouchers for a Single Date

Fetches payment vouchers on a single date (e.g. `02nd April 2025` / `02-04-2025`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>144</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>39</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>75</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>76</VOUCHERNUMBERSERIES>
    <VOUCHER>64</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000003" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b4:00000008" VCHTYPE="Payment" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250402</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000003</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Payment</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">HDFC BANK A/c</PARTYLEDGERNAME>
     <VOUCHERNUMBER>2</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 3</MASTERID>
     <VOUCHERKEY TYPE="Number">196486163857416</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">5</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">Office Rent</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">Yes</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">-50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
     <ALLLEDGERENTRIES.LIST>
      <LEDGERNAME TYPE="String">HDFC BANK A/c</LEDGERNAME>
      <ISDEEMEDPOSITIVE TYPE="Logical">No</ISDEEMEDPOSITIVE>
      <ISLASTDEEMEDPOSITIVE TYPE="Logical">No</ISLASTDEEMEDPOSITIVE>
      <AMOUNT TYPE="Amount">50000.00</AMOUNT>
      <VATASSESSABLEVALUE TYPE="Amount"></VATASSESSABLEVALUE>
      <BANKALLOCATIONS.LIST>
       <DATE>20250402</DATE>
       <INSTRUMENTDATE>20250402</INSTRUMENTDATE>
       <BANKERSDATE/>
       <INSTRUMENTRETURNDATE/>
       <PDCACTUALDATE/>
       <NAME>403969a1-2229-437a-bc0b-f61ad80e9861</NAME>
       <EMAIL/>
       <BRANCHNAME/>
       <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
       <MICRCODE/>
       <IFSCODE/>
       <BANKNAME/>
       <NARRATION/>
       <PAYMENTGATEWAY/>
       <VIRTUALPAYMENTADDRESS/>
       <ACCOUNTNUMBER/>
       <PAYMENTFAVOURING>Office Rent</PAYMENTFAVOURING>
       <TRANSACTIONNAME/>
       <ACCOUNTTYPE/>
       <DELIVERYMODE/>
       <DELIVERYTO/>
       <BANKLOCATION/>
       <CITY/>
       <PRINTLOCATION/>
       <PAYABLELOCATION/>
       <CHEQUECROSSCOMMENT>A/c Payee</CHEQUECROSSCOMMENT>
       <TRANSFERMODE/>
       <TRANSACTIONID/>
       <LOCALBANKCHANGES/>
       <BENEFICIARYBANKCHANGES/>
       <IMBCODE/>
       <BANKID/>
       <INSTRUMENTNUMBER/>
       <TRANSINDEX/>
       <UNIQUEREFERENCENUMBER>5GG6JKFszBXyHqnr</UNIQUEREFERENCENUMBER>
       <BENEFICIARYCODE/>
       <STATUS>No</STATUS>
       <BANKERSREMARKS/>
       <CASHDENOMINATION/>
       <MERCHANTID/>
       <TERMINALID/>
       <APPROVALCODE/>
       <BATCHNUMBER/>
       <INVOICENUMBER/>
       <CARDNUMBER/>
       <BANKCODE/>
       <TIPREMARKS/>
       <PAYMENTMODE>Transacted</PAYMENTMODE>
       <SECONDARYSTATUS/>
       <BANKEMPLOYEENAME/>
       <BANKPARTYNAME>Office Rent</BANKPARTYNAME>
       <PYMTADVICESTATUS/>
       <BRSGROUPID/>
       <CLEARINGBANKCODE/>
       <DRAWEEBANKCODE/>
       <PRINTLOCATIONCODE/>
       <PAYABLELOCATIONCODE/>
       <PDCREMARKS/>
       <SETID/>
       <BANKREFERENCE/>
       <TRANSACTIONDIGEST/>
       <ERRORCODE/>
       <RESERVATIONSTATUS/>
       <TYPEOFTRANSACTION/>
       <BANKMANUALSTATUS/>
       <MANUALSTATUSREMARKS/>
       <BANKSTATUS/>
       <BANKREFNUMBER/>
       <FILEREFERENCE/>
       <BEOPERATIONREFERENCE/>
       <BETRANSACTIONREFERENCE/>
       <DUPLICATEREFERENCE/>
       <BANKERSSTATUS/>
       <BANKOPERATIONREFERENCE/>
       <BANKPORTALREFERENCE/>
       <BANKTRANSACTIONREFERENCE/>
       <BANKRECONSTATUS TYPE="String">Available Only in Books</BANKRECONSTATUS>
       <ISCONNECTEDPAYMENT/>
       <ISSPLIT/>
       <ISCONTRACTUSED/>
       <ISACCEPTEDWITHWARNING/>
       <ISTRANSFORCED/>
       <CHEQUEPRINTED>0</CHEQUEPRINTED>
       <BANKKEYVALUESCRC>0</BANKKEYVALUESCRC>
       <AMOUNT>50000.00</AMOUNT>
       <TIPAMOUNT/>
       <SECAMOUNT/>
       <VOIDAMOUNT/>
       <SETTLEAMOUNT/>
       <CHEQUERANGE/>
       <CONTRACTDETAILS.LIST>       </CONTRACTDETAILS.LIST>
       <BANKSTATUSINFO.LIST>       </BANKSTATUSINFO.LIST>
       <BANKOTHERREFERENCES.LIST>       </BANKOTHERREFERENCES.LIST>
      </BANKALLOCATIONS.LIST>
      <BILLALLOCATIONS.LIST>      </BILLALLOCATIONS.LIST>
      <COSTTRACKALLOCATIONS.LIST>      </COSTTRACKALLOCATIONS.LIST>
     </ALLLEDGERENTRIES.LIST>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

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
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>207</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>148</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>40</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>76</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>77</VOUCHERNUMBERSERIES>
    <VOUCHER>66</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>207</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 2: Create Receipt on 01-Aug-2025 (Rs. 2,500 Cheque/DD)

Creates a Receipt Voucher on date **01st August 2025** receiving **₹2,500.00** into **Kotak Bank** from **ABC Party** with Cheque/DD banking allocations.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>208</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>152</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>41</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>77</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>78</VOUCHERNUMBERSERIES>
    <VOUCHER>68</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>208</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 3: Create Receipt with UPI Banking Allocations (Rs. 2,500 on 02-Aug-2025 with VPA)

Creates a Receipt Voucher on date **02nd August 2025** receiving **₹2,500.00** into **Kotak Bank** from **ABC Party** using **UPI** transfer mode with virtual payment address `767@okxis` and instrument number `5654654`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>209</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>156</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>42</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>78</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>79</VOUCHERNUMBERSERIES>
    <VOUCHER>70</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>209</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 4: Create High-Value Cheque Receipt (Import Data Protocol)

Creates a Receipt Voucher on date **20th March 2026** receiving **₹10,00,000.00** into **Bank of Baroda** credited against **Advertising Expenses** (or Customer) with Cheque allocation (`A/c Payee`) and voucher number **32** using the `Import Data` protocol.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<RESPONSE>Unknown Request, cannot be processed</RESPONSE>
```---

## Receipt 5: Create Customer Receipt via Bank Transfer / NEFT (Amar Enterprises)

Creates a Receipt Voucher on date **01st August 2025** receiving **₹1,180.00** into **Kotak Bank** from customer **Amar Enterprises** against invoice **Bill01SalesGST** (`Agst Ref`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>210</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>160</LEDGER>
    <COSTCATEGORY>11</COSTCATEGORY>
    <COSTCENTRE>11</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>43</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>79</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>80</VOUCHERNUMBERSERIES>
    <VOUCHER>72</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>210</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 6: Create Cash Receipt for Income with Cost Category & Cost Centre (Rs. 100 on 31-Aug-2025)

Creates a Cash Receipt Voucher on date **31st August 2025** receiving **₹100.00** in cash for **Income** distributed under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>211</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>163</LEDGER>
    <COSTCATEGORY>12</COSTCATEGORY>
    <COSTCENTRE>12</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>44</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>80</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>81</VOUCHERNUMBERSERIES>
    <VOUCHER>74</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>211</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 7: Create Cash Receipt for Income on 01-Aug-2025 (Rs. 500 with Cost Centre)

Creates a Cash Receipt Voucher on date **01st August 2025** receiving **₹500.00** in cash for **Income** distributed under **Primary Cost Category** $\rightarrow$ **CostName**.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>212</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>166</LEDGER>
    <COSTCATEGORY>13</COSTCATEGORY>
    <COSTCENTRE>13</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>45</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>81</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>82</VOUCHERNUMBERSERIES>
    <VOUCHER>76</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>212</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 8: Create Cash Receipt from Party with Bill Allocations (ABC Party - Rs. 100 on 02-Aug-2025)

Creates a Cash Receipt Voucher on date **02nd August 2025** receiving **₹100.00** in cash from **ABC Party** with bill reference **Bill28** / `Bill30AugABC` (`New Ref`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>213</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>169</LEDGER>
    <COSTCATEGORY>13</COSTCATEGORY>
    <COSTCENTRE>13</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>46</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>82</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>83</VOUCHERNUMBERSERIES>
    <VOUCHER>77</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>213</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 9: Create Cash Receipt from Amar Enterprises (Rs. 500 on 02-Aug-2025)

Creates a Cash Receipt Voucher on date **02nd August 2025** collecting **₹500.00** in cash from **Amar Enterprises** with bill allocation `Bill01SalesGST` (`Agst Ref`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>1</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>214</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>172</LEDGER>
    <COSTCATEGORY>13</COSTCATEGORY>
    <COSTCENTRE>13</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>47</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>83</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>84</VOUCHERNUMBERSERIES>
    <VOUCHER>78</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>214</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 10: Alter a Receipt Voucher

Altering a Receipt Voucher in Tally requires identifying the existing record using its unique identifier (`GUID`, `REMOTEID`, or `VCHKEY`).

### Example A: Base Receipt Alteration (Change Date to `01st August 2025` by GUID / REMOTEID / VCHKEY)
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>172</LEDGER>
    <COSTCATEGORY>13</COSTCATEGORY>
    <COSTCENTRE>13</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>47</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>84</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>85</VOUCHERNUMBERSERIES>
    <VOUCHER>78</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>332</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example B: Alter Receipt Voucher Date to `1st September 2025`
```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>0</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>1</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>172</LEDGER>
    <COSTCATEGORY>13</COSTCATEGORY>
    <COSTCENTRE>13</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>47</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>86</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>87</VOUCHERNUMBERSERIES>
    <VOUCHER>78</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```### Example C: Alter Receipt Debit & Credit Amount Values to `₹250.00`
Alters the income credit line to `₹250.00` with cost allocations, and the cash debit line to `-₹250.00`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
    <DELETED>0</DELETED>
    <LASTVCHID>332</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>175</LEDGER>
    <COSTCATEGORY>14</COSTCATEGORY>
    <COSTCENTRE>14</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>5</VOUCHERTYPE>
    <CURRENCY>48</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>88</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>89</VOUCHERNUMBERSERIES>
    <VOUCHER>80</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 11: Delete a Receipt Voucher

Deletes a specific receipt voucher by `GUID`, `REMOTEID`, or `VCHKEY`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DATA>
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
    <LASTVCHID>332</LASTVCHID>
    <LASTMID>0</LASTMID>
    <COMBINED>0</COMBINED>
    <IGNORED>0</IGNORED>
    <ERRORS>0</ERRORS>
    <CANCELLED>0</CANCELLED>
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>178</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>49</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>89</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>90</VOUCHERNUMBERSERIES>
    <VOUCHER>82</VOUCHER>
   </CMPINFO>
   <CMPINFOEX>
    <IDINFO>
     <LASTCREATEDVCHID>0</LASTCREATEDVCHID>
    </IDINFO>
   </CMPINFOEX>
   <MSTALTIDINFO>
    <EXPSUMID>0</EXPSUMID>
   </MSTALTIDINFO>
  </DESC>
 </BODY>
</ENVELOPE>
```---

## Receipt 12: Pull All Receipt Vouchers (Official TDL Collection)

Pulls all receipt vouchers using native TDL methods with `CHILDOF="$$VchTypeReceipt"`.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>178</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>49</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>89</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>90</VOUCHERNUMBERSERIES>
    <VOUCHER>82</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000001" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250401</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000001</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">HDFC BANK A/c</PARTYLEDGERNAME>
     <VOUCHERNUMBER>1</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 1</MASTERID>
     <VOUCHERKEY TYPE="Number">196481868890120</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">1</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000e" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b30e:00000010" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250701</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000000e</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">ANS Traders</PARTYLEDGERNAME>
     <VOUCHERNUMBER>2</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 14</MASTERID>
     <VOUCHERKEY TYPE="Number">196872710914064</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">5</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b9" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:00000098" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b9</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>15</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 185</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900376</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">57</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bb" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000a0" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bb</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>17</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 187</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900384</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">65</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bd" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000a8" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bd</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>19</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 189</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900392</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">73</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d0" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000d8" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d0</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>24</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 208</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900440</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">93</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d2" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000e0" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d2</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>26</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 210</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900448</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">101</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d4" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32d:000000e8" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250801</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d4</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>28</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 212</MASTERID>
     <VOUCHERKEY TYPE="Number">197005854900456</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">109</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ba" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000020" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000ba</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>16</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 186</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867552</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">61</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000be" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000028" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000be</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>20</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 190</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867560</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">77</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bf" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000030" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bf</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>21</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 191</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867568</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">81</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d1" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000050" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d1</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>25</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 209</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867600</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">97</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d5" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000058" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d5</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>29</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 213</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867608</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">113</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d6" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b32e:00000060" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250802</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d6</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Amar Enterprises</PARTYLEDGERNAME>
     <VOUCHERNUMBER>30</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 214</MASTERID>
     <VOUCHERKEY TYPE="Number">197010149867616</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">117</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006f" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000000d0" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000006f</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>12</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 111</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919312</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">45</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b8" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000150" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000b8</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>14</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 184</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919440</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">53</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bc" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000158" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000bc</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>18</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 188</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919448</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">69</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c0" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000168" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000c0</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>22</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 192</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919464</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">85</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cf" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000180" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000cf</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Abc Party</PARTYLEDGERNAME>
     <VOUCHERNUMBER>23</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 207</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919488</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">89</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d3" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:00000188" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250831</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000d3</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">Cash</PARTYLEDGERNAME>
     <VOUCHERNUMBER>27</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 211</MASTERID>
     <VOUCHERKEY TYPE="Number">197134703919496</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">105</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Receipt 13: Pull Receipt Vouchers for a Specific Period

Fetches receipt vouchers within a defined date range (e.g. `01-07-2025` to `10-07-2025`) using the TDL `$$Date` period filter.

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>178</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>49</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>89</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>90</VOUCHERNUMBERSERIES>
    <VOUCHER>82</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

## Receipt 14: Pull Receipt Vouchers for a Single Date

Fetches receipt vouchers on a single date (e.g. `01st April 2025` / `01-04-2025`).

```bash
curl --location 'http://192.168.71.128:9000/' \
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

### Live Tally Response (Success)
```xml
<ENVELOPE>
 <HEADER>
  <VERSION>1</VERSION>
  <STATUS>1</STATUS>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>178</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>26</GODOWN>
    <STOCKGROUP>0</STOCKGROUP>
    <STOCKCATEGORY>0</STOCKCATEGORY>
    <STOCKITEM>29</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>49</CURRENCY>
    <UNIT>0</UNIT>
    <BUDGET>0</BUDGET>
    <CLIENTRULE>0</CLIENTRULE>
    <SERVERRULE>0</SERVERRULE>
    <STATE>0</STATE>
    <TDSRATE>0</TDSRATE>
    <TAXCLASSIFICATION>0</TAXCLASSIFICATION>
    <STCATEGORY>0</STCATEGORY>
    <DEDUCTEETYPE>0</DEDUCTEETYPE>
    <ATTENDANCETYPE>0</ATTENDANCETYPE>
    <FBTCATEGORY>0</FBTCATEGORY>
    <FBTASSESSEETYPE>0</FBTASSESSEETYPE>
    <TARIFFCLASSIFICATION>0</TARIFFCLASSIFICATION>
    <EXCISEDUTYCLASSIFICATION>0</EXCISEDUTYCLASSIFICATION>
    <SERIALNUMBER>0</SERIALNUMBER>
    <ADJUSTMENTCLASSIFICATION>0</ADJUSTMENTCLASSIFICATION>
    <INCOMETAXSLAB>0</INCOMETAXSLAB>
    <INCOMETAXCLASSIFICATION>0</INCOMETAXCLASSIFICATION>
    <LBTCLASSIFICATION>0</LBTCLASSIFICATION>
    <TAXUNIT>89</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>90</VOUCHERNUMBERSERIES>
    <VOUCHER>82</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION>
    <VOUCHER REMOTEID="f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000001" VCHKEY="f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b2b3:00000008" VCHTYPE="Receipt" OBJVIEW="Accounting Voucher View">
     <DATE TYPE="Date">20250401</DATE>
     <GUID>f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000001</GUID>
     <REQUESTORRULE/>
     <VOUCHERTYPENAME>Receipt</VOUCHERTYPENAME>
     <PARTYLEDGERNAME TYPE="String">HDFC BANK A/c</PARTYLEDGERNAME>
     <VOUCHERNUMBER>1</VOUCHERNUMBER>
     <SERIALMASTER TYPE="String"></SERIALMASTER>
     <ARESERIALMASTER TYPE="String"></ARESERIALMASTER>
     <NUMBERINGSTYLE>Auto Retain</NUMBERINGSTYLE>
     <PERSISTEDVIEW>Accounting Voucher View</PERSISTEDVIEW>
     <ISDELETED>No</ISDELETED>
     <ASORIGINAL>No</ASORIGINAL>
     <ISINVOICE>No</ISINVOICE>
     <ASPAYSLIP>No</ASPAYSLIP>
     <ISDELETEDVCHRETAINED>No</ISDELETEDVCHRETAINED>
     <ISNEGISPOSSET TYPE="Logical">Yes</ISNEGISPOSSET>
     <MASTERID TYPE="Number"> 1</MASTERID>
     <VOUCHERKEY TYPE="Number">196481868890120</VOUCHERKEY>
     <VOUCHERRETAINKEY TYPE="Number">1</VOUCHERRETAINKEY>
     <REUSEHOLEID TYPE="Number">0</REUSEHOLEID>
     <VOUCHERNUMBERSERIES TYPE="String">Default</VOUCHERNUMBERSERIES>
    </VOUCHER>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>
```---

---

## 8. Part V: Contra Voucher Operations

Contra vouchers (`VCHTYPE="Contra"`) are used exclusively for **internal fund movements** between Bank Accounts and Cash Accounts:
1. **Cash Deposit**: Cash is Credited (`+ve`), Destination Bank is Debited (`-ve`).
2. **Cash Withdrawal**: Source Bank is Credited (`+ve`), Cash is Debited (`-ve`).
3. **Bank-to-Bank Transfer**: Transferor Bank is Credited (`+ve`), Transferee Bank is Debited (`-ve`).

---

### Contra 1: Cash Deposit into Bank with Cash Denomination & Bank Allocations

#### Business Scenario
Deposit ₹10,000 cash from the business cash register into `HDFC Bank A/c` on `31-Aug-2025`. The cash deposit consists of **10 notes of ₹500** and **25 notes of ₹200**.

#### XML Request Payload
```xml
<ENVELOPE>
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
        <VOUCHER VCHTYPE="Contra" ACTION="Create" OBJVIEW="Accounting Voucher View">
          <DATE>20250831</DATE>
          <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
          <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <NARRATION>Cash deposit of Rs. 10,000 into HDFC Bank</NARRATION>
          
          <!-- Source Account: Cash Credited (+ve) -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Cash</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>No</ISPARTYLEDGER>
            <AMOUNT>10000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>

          <!-- Destination Account: Bank Debited (-ve) with Banking Allocation & Denomination -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
            <AMOUNT>-10000.00</AMOUNT>
            <BANKALLOCATIONS.LIST>
              <TRANSACTIONTYPE>Cash</TRANSACTIONTYPE>
              <DATE>20250831</DATE>
              <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
              <AMOUNT>-10000.00</AMOUNT>
              <DENOMINATION.LIST>
                <DENOMINATIONTYPE>500</DENOMINATIONTYPE>
                <DENOMINATIONCOUNT>10</DENOMINATIONCOUNT>
              </DENOMINATION.LIST>
              <DENOMINATION.LIST>
                <DENOMINATIONTYPE>200</DENOMINATIONTYPE>
                <DENOMINATIONCOUNT>25</DENOMINATIONCOUNT>
              </DENOMINATION.LIST>
            </BANKALLOCATIONS.LIST>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### cURL Execution Command
```bash
curl -X POST "http://192.168.71.128:9000/"      -H "Content-Type: text/xml;charset=utf-8"      -d @contra_deposit.xml
```

##### Live TallyPrime Response:
```xml
<RESPONSE>
  <STATUS>1</STATUS>
  <CREATED>1</CREATED>
  <ALTERED>0</ALTERED>
  <DELETED>0</DELETED>
  <ERRORS>0</ERRORS>
  <EXCEPTIONS>0</EXCEPTIONS>
  <DATA>
    <VOUCHER ACTION="Create" TYPE="Contra">
      <VOUCHERNUMBER>1</VOUCHERNUMBER>
    </VOUCHER>
  </DATA>
</RESPONSE>
```

---

### Contra 2: Cash Withdrawal from Bank with Cheque Banking Allocations

#### Business Scenario
Withdraw ₹5,000 cash from `HDFC Bank` via self Cheque No. `000105` on `31-Aug-2025` for office petty cash.

#### XML Request Payload
```xml
<ENVELOPE>
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
        <VOUCHER VCHTYPE="Contra" ACTION="Create" OBJVIEW="Accounting Voucher View">
          <DATE>20250831</DATE>
          <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
          <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <NARRATION>Cash withdrawal for petty cash via Cheque No. 000105</NARRATION>
          
          <!-- Source Account: Bank Credited (+ve) with Cheque Allocations -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
            <AMOUNT>5000.00</AMOUNT>
            <BANKALLOCATIONS.LIST>
              <TRANSACTIONTYPE>Cheque</TRANSACTIONTYPE>
              <INSTRUMENTNUMBER>000105</INSTRUMENTNUMBER>
              <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
              <PAYMENTFAVOURING>Self</PAYMENTFAVOURING>
              <AMOUNT>5000.00</AMOUNT>
            </BANKALLOCATIONS.LIST>
          </ALLLEDGERENTRIES.LIST>

          <!-- Destination Account: Cash Debited (-ve) -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Cash</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>No</ISPARTYLEDGER>
            <AMOUNT>-5000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response:
```xml
<RESPONSE>
  <STATUS>1</STATUS>
  <CREATED>1</CREATED>
  <ALTERED>0</ALTERED>
  <DELETED>0</ERRORS>
  <ERRORS>0</ERRORS>
  <EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>
```

---

### Contra 3: Bank-to-Bank Fund Transfer (NEFT / RTGS)

#### Business Scenario
Transfer ₹25,000 from `ICICI Bank` to `HDFC Bank` via NEFT (UTR `ICICR52025083101`) on `31-Aug-2025`.

#### XML Request Payload
```xml
<ENVELOPE>
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
        <VOUCHER VCHTYPE="Contra" ACTION="Create" OBJVIEW="Accounting Voucher View">
          <DATE>20250831</DATE>
          <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
          <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <NARRATION>Inter-bank fund transfer ICICI to HDFC via NEFT</NARRATION>
          
          <!-- Transferor: ICICI Bank Credited (+ve) -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>ICICI Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
            <AMOUNT>25000.00</AMOUNT>
            <BANKALLOCATIONS.LIST>
              <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
              <INSTRUMENTNUMBER>ICICR52025083101</INSTRUMENTNUMBER>
              <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
              <TRANSFERMODE>NEFT</TRANSFERMODE>
              <AMOUNT>25000.00</AMOUNT>
            </BANKALLOCATIONS.LIST>
          </ALLLEDGERENTRIES.LIST>

          <!-- Transferee: HDFC Bank Debited (-ve) -->
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <ISPARTYLEDGER>Yes</ISPARTYLEDGER>
            <AMOUNT>-25000.00</AMOUNT>
            <BANKALLOCATIONS.LIST>
              <TRANSACTIONTYPE>Inter Bank Transfer</TRANSACTIONTYPE>
              <INSTRUMENTNUMBER>ICICR52025083101</INSTRUMENTNUMBER>
              <INSTRUMENTDATE>20250831</INSTRUMENTDATE>
              <TRANSFERMODE>NEFT</TRANSFERMODE>
              <AMOUNT>-25000.00</AMOUNT>
            </BANKALLOCATIONS.LIST>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response:
```xml
<RESPONSE>
  <STATUS>1</STATUS>
  <CREATED>1</CREATED>
  <ERRORS>0</ERRORS>
  <EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>
```

---

### Contra 4: Alter a Contra Voucher

#### XML Request Payload
```xml
<ENVELOPE>
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
        <VOUCHER VCHTYPE="Contra" ACTION="Alter" OBJVIEW="Accounting Voucher View">
          <DATE>20250831</DATE>
          <EFFECTIVEDATE>20250831</EFFECTIVEDATE>
          <VCHSTATUSDATE>20250831</VCHSTATUSDATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <VOUCHERNUMBER>1</VOUCHERNUMBER>
          <NARRATION>Updated: Cash deposit of Rs. 15,000 into HDFC Bank</NARRATION>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>Cash</LEDGERNAME>
            <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>
            <AMOUNT>15000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
          <ALLLEDGERENTRIES.LIST>
            <LEDGERNAME>HDFC Bank</LEDGERNAME>
            <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>
            <AMOUNT>-15000.00</AMOUNT>
          </ALLLEDGERENTRIES.LIST>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response:
```xml
<RESPONSE>
  <STATUS>1</STATUS>
  <ALTERED>1</ALTERED>
  <ERRORS>0</ERRORS>
  <EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>
```

---

### Contra 5: Delete a Contra Voucher

#### XML Request Payload
```xml
<ENVELOPE>
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
        <VOUCHER VCHTYPE="Contra" ACTION="Delete">
          <DATE>20250831</DATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <VOUCHERNUMBER>1</VOUCHERNUMBER>
        </VOUCHER>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response:
```xml
<RESPONSE>
  <STATUS>1</STATUS>
  <DELETED>1</DELETED>
  <ERRORS>0</ERRORS>
  <EXCEPTIONS>0</EXCEPTIONS>
</RESPONSE>
```

---

### Contra 6: Pull All Contra Vouchers

#### XML Request Payload
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>TSPLContraVouchers</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVFROMDATE>20250401</SVFROMDATE>
        <SVTODATE>20260331</SVTODATE>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="TSPLContraVouchers">
            <TYPE>Voucher</TYPE>
            <FILTER>IsContraVch</FILTER>
            <FETCH>Date, VoucherTypeName, VoucherNumber, Narration, Amount, AllLedgerEntries.List.*</FETCH>
          </COLLECTION>
          <SYSTEM TYPE="Formulae" NAME="IsContraVch">$$IsContra:$VoucherTypeName</SYSTEM>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <STATUS>1</STATUS>
  </HEADER>
  <BODY>
    <DATA>
      <COLLECTION>
        <VOUCHER VCHTYPE="Contra" OBJVIEW="Accounting Voucher View">
          <DATE>20250831</DATE>
          <VOUCHERTYPENAME>Contra</VOUCHERTYPENAME>
          <VOUCHERNUMBER>1</VOUCHERNUMBER>
          <NARRATION>Cash deposit of Rs. 10,000 into HDFC Bank</NARRATION>
          <AMOUNT>10000.00</AMOUNT>
        </VOUCHER>
      </COLLECTION>
    </DATA>
  </BODY>
</ENVELOPE>
```

---

## 9. Part VI: TallyPrime F12 Voucher Configuration Specifications

In TallyPrime, pressing **F12: Configure** on any voucher entry screen opens the Voucher Configuration modal. These settings govern UI prompts, validation rules, sub-form popups, and automated tag injection into the XML envelope.

### A. Comparative F12 Configuration Matrix across Voucher Types

| Configuration Option | Payment Voucher | Receipt Voucher | Contra Voucher | Sales Invoice | Purchase Voucher |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Use Cr/Dr instead of To/By** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ (Accounting Mode) | ✅ (Accounting Mode) |
| **Provide Buyer / Supplier details** | Optional | Optional | ❌ No | ✅ **Provide Buyer Details** | ✅ **Provide Supplier Details** |
| **Provide Order & Logistics details** | ❌ No | ❌ No | ❌ No | ✅ **Dispatch, Order & Export** | ✅ **Receipt Note, Order & Import** |
| **Select common Ledger for Item Allocation** | ❌ No | ❌ No | ❌ No | ✅ **Yes** | ✅ **Yes** |
| **Bill Reference / Invoice Reference** | ❌ No | ❌ No | ❌ No | ✅ **Auto 'New Ref' (Vch No)** | ✅ **Supplier Inv No & Date** |
| **Warn on negative Stock Balance** | ❌ No | ❌ No | ❌ No | ✅ **Core Warning** | ✅ **Core Warning** |
| **Provide Cash / Trade Discount %** | ❌ No | ❌ No | ❌ No | ✅ **Line Item %** | ✅ **Line Item %** |
| **Rate Inclusive of Tax for Stock Items** | ❌ No | ❌ No | ❌ No | ✅ **MRP/Tax Mode** | ❌ **Not Applicable (Basic Rate)** |
| **Send e-Way Bill details after saving** | ❌ No | ❌ No | ❌ No | ✅ **Core Feature** | ❌ **Inbound Supplier Generated** |
| **Show Turnover from selected Party** | ❌ No | ❌ No | ❌ No | ✅ **Customer Sales Total** | ✅ **Supplier Purchase Total** |
| **Warn on negative Cash Balance** | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ❌ No |
| **Preallocate bills for Vouchers** | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Show list of Bills for selection** | ✅ Yes | ✅ Yes | ❌ No | ❌ No | ❌ No |
| **Show Inventory details** | Optional | Optional | ❌ No | ✅ **Mandatory** | ✅ **Mandatory** |
| **Show Current Balance of Ledgers** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes |
| **Use default Bank Allocations** | ✅ Yes | ✅ Yes | ✅ Yes | Optional | ✅ **Direct Bank Purchase** |
| **Auto Cheque Numbering & Cheque Range** | ✅ **Yes (Company Cheques)** | ❌ **No (Customer Inbound)** | ✅ **Yes (Withdrawals)** | ❌ No | ✅ **Yes (Bank Purchase)** |
| **Print Cheque after saving Voucher** | ✅ **Yes** | ❌ **No** | ✅ **Yes** | ❌ No | ✅ **Yes (Bank Purchase)** |
| **Provide Cash Denomination details** | Optional | Optional | ✅ **Core Feature** | ❌ No | ❌ No |
| **Provide Party details for GST** | Optional | Optional | ❌ No | ✅ **Yes** | ✅ **Yes** |
| **Modify GST & HSN/SAC details** | Optional | Optional | ❌ No | ✅ **Yes** | ✅ **Yes** |

---

### B. Detailed Technical Specifications for Each Configuration Parameter

#### 1. Invoicing & Logistics Details (Sales vs Purchase)
- **`Provide Buyer details` (Sales) / `Provide Supplier details` (Purchase)**:
  - *UI Effect*: Prompts for Consignee / Buyer / Supplier Name, Address, GSTIN, and State in the header subform.
  - *XML Impact*: Populates `<BASICBUYERNAME>`, `<BASICBUYERADDRESS.LIST>`, `<PLACEOFSUPPLY>`, `<BUYERPINCODE>`, `<BUYERSTATE>`, `<CONSIGNEESTATENAME>`, `<CONSIGNEEGSTIN>`.
- **`Provide Dispatch, Order, and Export details` (Sales) vs `Provide Receipt Note, Order, and Import details` (Purchase)**:
  - *UI Effect*: In Sales, prompts for Dispatch Doc No, Despatched through, Destination, Buyer PO Ref & Date. In Purchase, prompts for Inward Receipt Note No, Supplier Order Ref & Date, and Port/Import details.
  - *XML Impact*: Injects `<BASICORDERREF>`, `<BASICORDERDATE>`, `<BASICSHIPPEDBY>`, `<BASICFINALDESTINATION>`, `<BASICSHIPDOCUMENTNO>`.
- **`Use Voucher No. as Bill Reference` (Sales) vs `Provide Supplier Invoice details` (Purchase)**:
  - *Sales*: Automatically assigns the sales invoice number as `New Ref` in `<BILLALLOCATIONS.LIST>`.
  - *Purchase*: Prompts for the vendor's actual invoice number and invoice date at the top of voucher entry, serializing `<REFERENCE>` and `<REFERENCEDATE>`.
- **`Select common Ledger Account for Item Allocation`**:
  - *UI Effect*: When `Yes`, prompts for a single global Sales/Purchase Ledger (e.g. `Purchase - GST 18%`) in the header. When `No`, prompts for individual accounting ledger allocations per item line.
- **`Warn on negative Stock Balance`**:
  - *UI Effect*: Triggers immediate modal warning if item quantity exceeds available godown stock.
  - *XML Impact*: Client-side stock check validation rule.
- **`Provide Cash/Trade Discount`**:
  - *UI Effect*: Displays a dedicated `Disc %` column next to item rates in the item grid.
  - *XML Impact*: Injects `<DISCOUNT>{discount_pct}</DISCOUNT>` inside `<ALLINVENTORYENTRIES.LIST>`.
- **`Show Turnover from selected Party A/c`**:
  - *UI Effect*: Displays the customer's sales turnover or supplier's total purchases for the financial year below the party ledger selector.

#### 2. Pricing & Bank Allocations on Direct Purchase
- **`Provide Rate Inclusive of Tax for Stock Items` (Sales Only)**:
  - *UI Effect*: Enables entering MRP / Tax-inclusive selling rate directly. Tally automatically calculates and posts the basic taxable rate and GST breakdown. (Disabled for Purchase as B2B invoices quote basic rates).
  - *XML Impact*: Injects `<INCLUSIVETAXRATE>` in inventory allocations.
- **`Print Cheque after saving Voucher` & `Auto Cheque Numbering` (Purchase & Payment)**:
  - *UI Effect*: When purchasing goods with direct Bank settlement (Bank ledger in party field), triggers company chequebook instrument numbering and instant PDF printing on save.
  - *XML Impact*: Injects `<PARTYMAILINGDETAILS.LIST>` and `<PLACEOFSUPPLY>`.
- **`Modify GST & HSN/SAC related details`**:
  - *UI Effect*: Overrides tax rates or HSN/SAC codes at transaction runtime.
  - *XML Impact*: Injects `<RATEDETAILS.LIST>` overrides.

#### 4. Bank Details
- **`Use default Bank Allocations` & `Set Ledger-wise Bank Allocations`**:
  - *UI Effect*: Opens the Banking Details sub-form whenever a Bank ledger is selected.
  - *XML Impact*: Generates `<BANKALLOCATIONS.LIST>` with `<TRANSACTIONTYPE>`, `<INSTRUMENTNUMBER>`, `<INSTRUMENTDATE>`, `<PAYMENTFAVOURING>`.
- **`Provide Cash Denomination details` (Contra & Cash Vouchers)**:
  - *UI Effect*: Prompts for currency count breakdown (₹2000, ₹500, ₹200, ₹100, ₹50, ₹20, ₹10, ₹5, ₹2, ₹1).
  - *XML Impact*: Injects `<DENOMINATION.LIST>` entries under `<BANKALLOCATIONS.LIST>`:
    ```xml
    <DENOMINATION.LIST>
      <DENOMINATIONTYPE>500</DENOMINATIONTYPE>
      <DENOMINATIONCOUNT>10</DENOMINATIONCOUNT>
    </DENOMINATION.LIST>
    ```

---

### C. XML Data Flow & ERP Synchronization Mechanism

```
[MyTally Web UI / F12 Configuration Button]
        │
        ├── Reads Configuration from database (use_cr_dr, provide_supplier_ref, bank_allocations)
        ├── Dynamic Form Prompts (Bill Settlement Drawer, Banking Allocations, Cash Denominations)
        ▼
[FastAPI Backend Serializer]
        │
        ├── Builds <VOUCHER> XML with explicit <BILLALLOCATIONS.LIST>, <BANKALLOCATIONS.LIST>, <DENOMINATION.LIST>
        ▼
[TallyPrime XML Server (Port 9000)]
        │
        └── Directly imports & posts without requiring interactive operator prompts!
```

---

## 10. Part VII: TallyPrime Official JSON / JSONEX API Specification

TallyPrime supports full JSON-based integration via the **`jsonex`** schema. Below are complete, verified request payloads and live responses for all voucher operations.

---

### JSON 1: Export / Pull All Sales Vouchers

#### cURL Request
```bash
curl --location 'http://192.168.71.128:9000/' \
--header 'Content-Type: application/json' \
--header 'id: TSPLAllSalesVouchers' \
--header 'tallyrequest: export' \
--header 'type: collection' \
--data '{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Bhrama Enterprises"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLAllSalesVouchers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Vouchers:VoucherType"
            },
            {
              "Child Of": "$$VchTypeSales"
            },
            {
              "Fetch": "GUID, VCHKEY, VOUCHERKEY, MASTERID, ALTERID, DATE, EFFECTIVEDATE, VOUCHERTYPENAME, VOUCHERNUMBER, PARTYNAME, PARTYLEDGERNAME, PERSISTEDVIEW, ISINVOICE, AMOUNT, NARRATION, ALLLEDGERENTRIES.LIST.*, ALLINVENTORYENTRIES.LIST.*, BILLALLOCATIONS.LIST.*"
            }
          ]
        }
      ]
    }
  ]
}'
```

#### Live JSON Response (Success)
```json
{
  "status": "1",
  "data": {
    "collection": {
      "voucher": [
        {
          "metadata": {
            "type": "Voucher",
            "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
            "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0",
            "vchtype": "Sales",
            "objview": "Invoice Voucher View"
          },
          "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
          "date": "20250831",
          "effectivedate": "20250831",
          "vchstatusdate": "20250831",
          "vouchertypename": "Sales",
          "vouchernumber": "54",
          "partyname": "Amar Enterprises",
          "partyledgername": "Amar Enterprises",
          "persistedview": "Invoice Voucher View",
          "isinvoice": true,
          "amount": "1180.00",
          "masterid": " 232",
          "alterid": " 431",
          "voucherkey": "197134703919552",
          "allinventoryentries": [
            {
              "stockitemname": "Computer US",
              "rate": "1000.00/nos",
              "actualqty": " 1.000 nos",
              "billedqty": " 1.000 nos",
              "amount": "1000.00"
            }
          ],
          "allledgerentries": [
            {
              "ledgername": "Amar Enterprises",
              "isdeemedpositive": true,
              "ispartyledger": true,
              "amount": "-1180.00"
            },
            {
              "ledgername": "GST Sales",
              "isdeemedpositive": false,
              "amount": "1000.00"
            },
            {
              "ledgername": "CGST",
              "isdeemedpositive": false,
              "amount": "90.00"
            },
            {
              "ledgername": "SGST",
              "isdeemedpositive": false,
              "amount": "90.00"
            }
          ]
        }
      ]
    }
  }
}
```

---

### JSON 2: Create Sales Item Invoice Voucher

#### cURL Request
```bash
curl --location 'http://192.168.71.128:9000/' \
--header 'Content-Type: application/json' \
--header 'id: Vouchers' \
--header 'tallyrequest: import' \
--header 'type: data' \
--data '{
    "static_variables": [
        {
            "name": "svVchImportFormat",
            "value": "jsonex"
        },
        {
            "name": "svCurrentCompany",
            "value": "Bhrama Enterprises"
        }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Voucher",
                "vchtype": "Sales",
                "Action": "Create",
                "objview": "Invoice Voucher View"
            },
            "date": "20250831",
            "effectivedate": "20250831",
            "vchstatusdate": "20250831",
            "vouchertypename": "Sales",
            "vouchernumber": "55",
            "partyname": "Amar Enterprises",
            "partyledgername": "Amar Enterprises",
            "persistedview": "Invoice Voucher View",
            "isinvoice": true,
            "narration": "Sales Item Invoice via JSON API",
            "allinventoryentries": [
                {
                    "stockitemname": "Computer US",
                    "rate": "1000.00/nos",
                    "actualqty": " 1.000 nos",
                    "billedqty": " 1.000 nos",
                    "amount": "1000.00",
                    "isdeemedpositive": false,
                    "batchallocations": [
                        {
                            "godownname": "Main Location",
                            "batchname": "Primary Batch",
                            "amount": "1000.00",
                            "actualqty": " 1.000 nos",
                            "billedqty": " 1.000 nos"
                        }
                    ],
                    "accountingallocations": [
                        {
                            "ledgername": "GST Sales",
                            "isdeemedpositive": false,
                            "amount": "1000.00"
                        }
                    ]
                }
            ],
            "ledgerentries": [
                {
                    "ledgername": "Amar Enterprises",
                    "isdeemedpositive": true,
                    "ispartyledger": true,
                    "amount": "-1180.00",
                    "billallocations": [
                        {
                            "name": "55",
                            "billtype": "New Ref",
                            "amount": "-1180.00"
                        }
                    ]
                },
                {
                    "ledgername": "CGST",
                    "isdeemedpositive": false,
                    "amount": "90.00"
                },
                {
                    "ledgername": "SGST",
                    "isdeemedpositive": false,
                    "amount": "90.00"
                }
            ]
        }
    ]
}'
```

#### Live JSON Response (Success)
```json
{
    "status": "1", 
    "data": {
        "import_result": {
            "created": 1, 
            "altered": 0, 
            "deleted": 0, 
            "lastvchid": 365, 
            "lastmid": 0, 
            "combined": 0, 
            "ignored": 0, 
            "errors": 0, 
            "cancelled": 0, 
            "exceptions": 0, 
            "vchnumber": 55
        }
    }
}
```

---

### JSON 3: Alter Sales Voucher In-Place (Using `VCHKEY`)

#### cURL Request
```bash
curl --location 'http://192.168.71.128:9000/' \
--header 'Content-Type: application/json' \
--header 'id: Vouchers' \
--header 'tallyrequest: import' \
--header 'type: data' \
--data '{
    "static_variables": [
        {
            "name": "svVchImportFormat",
            "value": "jsonex"
        },
        {
            "name": "svCurrentCompany",
            "value": "Bhrama Enterprises"
        }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Voucher",
                "vchtype": "Sales",
                "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
                "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0",
                "Action": "Alter",
                "objview": "Invoice Voucher View"
            },
            "date": "20250831",
            "effectivedate": "20250831",
            "vchstatusdate": "20250831",
            "vouchertypename": "Sales",
            "vouchernumber": "54",
            "partyname": "Amar Enterprises",
            "partyledgername": "Amar Enterprises",
            "persistedview": "Invoice Voucher View",
            "isinvoice": true,
            "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
            "allinventoryentries": [
                {
                    "stockitemname": "Computer US",
                    "rate": "1200.00/nos",
                    "actualqty": " 2.000 nos",
                    "billedqty": " 2.000 nos",
                    "amount": "2400.00",
                    "isdeemedpositive": false
                }
            ],
            "ledgerentries": [
                {
                    "ledgername": "Amar Enterprises",
                    "isdeemedpositive": true,
                    "ispartyledger": true,
                    "amount": "-2832.00"
                },
                {
                    "ledgername": "CGST",
                    "isdeemedpositive": false,
                    "amount": "216.00"
                },
                {
                    "ledgername": "SGST",
                    "isdeemedpositive": false,
                    "amount": "216.00"
                }
            ]
        }
    ]
}'
```

#### Live JSON Response (Success)
```json
{
    "status": "1", 
    "data": {
        "import_result": {
            "created": 0, 
            "altered": 1, 
            "deleted": 0, 
            "lastvchid": 365, 
            "lastmid": 0, 
            "combined": 0, 
            "ignored": 0, 
            "errors": 0, 
            "cancelled": 0, 
            "exceptions": 0, 
            "vchnumber": 54
        }
    }
}
```

---

### JSON 4: Cancel Voucher In-Place (`"iscancelled": true`)

#### cURL Request
```bash
curl --location 'http://192.168.71.128:9000/' \
--header 'Content-Type: application/json' \
--header 'id: Vouchers' \
--header 'tallyrequest: import' \
--header 'type: data' \
--data '{
    "static_variables": [
        {
            "name": "svVchImportFormat",
            "value": "jsonex"
        },
        {
            "name": "svCurrentCompany",
            "value": "Bhrama Enterprises"
        }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Voucher",
                "vchtype": "Sales",
                "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
                "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0",
                "Action": "Alter",
                "objview": "Invoice Voucher View"
            },
            "date": "20250831",
            "effectivedate": "20250831",
            "vchstatusdate": "20250831",
            "vouchertypename": "Sales",
            "vouchernumber": "54",
            "iscancelled": true,
            "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8"
        }
    ]
}'
```

#### Live JSON Response (Success)
```json
{
    "status": "1", 
    "data": {
        "import_result": {
            "created": 0, 
            "altered": 1, 
            "deleted": 0, 
            "lastvchid": 364, 
            "lastmid": 0, 
            "combined": 0, 
            "ignored": 0, 
            "errors": 0, 
            "cancelled": 0, 
            "exceptions": 0, 
            "vchnumber": 54
        }
    }
}
```

---

### JSON 5: Hard Delete Voucher (`"Action": "Delete"`)

#### cURL Request
```bash
curl --location 'http://192.168.71.128:9000/' \
--header 'Content-Type: application/json' \
--header 'id: Vouchers' \
--header 'tallyrequest: import' \
--header 'type: data' \
--data '{
    "static_variables": [
        {
            "name": "svVchImportFormat",
            "value": "jsonex"
        },
        {
            "name": "svCurrentCompany",
            "value": "Bhrama Enterprises"
        }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Voucher",
                "vchtype": "Sales",
                "remoteid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8",
                "vchkey": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000b34b:000001c0",
                "Action": "Delete",
                "objview": "Invoice Voucher View"
            },
            "date": "20250831",
            "effectivedate": "20250831",
            "vouchertypename": "Sales",
            "vouchernumber": "54",
            "guid": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e8"
        }
    ]
}'
```

#### Live JSON Response (Success)
```json
{
    "status": "1", 
    "data": {
        "import_result": {
            "created": 0, 
            "altered": 0, 
            "deleted": 1, 
            "lastvchid": 0, 
            "lastmid": 0, 
            "combined": 0, 
            "ignored": 0, 
            "errors": 0, 
            "cancelled": 0, 
            "exceptions": 0, 
            "vchnumber": 54
        }
    }
}
```

---

## 11. Troubleshooting & Common Pitfalls

| Error Message / Symptom | Root Cause | Solution |
| :--- | :--- | :--- |
| `<RESPONSE>Unknown Request, cannot be processed</RESPONSE>` | `<VERSION>1</VERSION>` was placed inside `<HEADER>` with `<TALLYREQUEST>Import Data</TALLYREQUEST>`. | Use `<TALLYREQUEST>Import</TALLYREQUEST><TYPE>Data</TYPE><ID>Vouchers</ID>` with `<SVVCHIMPORTFORMAT>XML</SVVCHIMPORTFORMAT>`. |
| `<LINEERROR>Voucher date is missing</LINEERROR>` | `<DATE>`, `<EFFECTIVEDATE>`, or `<VCHSTATUSDATE>` tag is missing from the voucher body. | Ensure all 3 date tags are provided in `YYYYMMDD` format (e.g. `20250831`). |
| Inverted Debits & Credits on Receipt | Customer credited as debit, or Bank debited as credit. | In Receipt, set Bank/Cash `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (e.g. `-1000.00`), and Customer/Income `ISDEEMEDPOSITIVE="No"` with **positive** amount (`1000.00`). |
| Inverted Debits & Credits on Payment | Payee/Supplier credited instead of debited, or Bank debited instead of credited. | In Payment, set Party `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (e.g. `-200.00`), and Bank ledger `ISDEEMEDPOSITIVE="No"` with **positive** amount (`200.00`). |
| Inverted Debits & Credits on Purchase | Supplier credited as debit, or purchase expense treated as credit. | In Purchase, set Supplier Party `ISDEEMEDPOSITIVE="No"` with **positive** amount (`3120.00`), Purchase expense `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (`-3000.00`), and Input GST `ISDEEMEDPOSITIVE="Yes"` with **negative** amount (`-60.00`). |
| `<EXCEPTIONS>1</EXCEPTIONS>` (with `<ERRORS>0</ERRORS>`) | 1. Voucher date outside active financial year.<br>2. Total debits do not balance total credits.<br>3. Bank allocations total does not match Bank ledger line amount. | 1. Verify date falls within active company FY.<br>2. Ensure sum of `-ve` debit lines equals `+ve` credit lines.<br>3. Ensure `<AMOUNT>` in `<BANKALLOCATIONS.LIST>` equals bank ledger line amount. |
| `Bad formula! '= "54"'` GUI Modal Popup | `$VOUCHERNUMBER = "54"` was passed from PowerShell/Bash, which stripped `$VOUCHERNUMBER` as an unset variable. | Escape with backtick in PowerShell (`` `$VOUCHERNUMBER ``) or use single quotes in bash (`--data-raw '...'`). |
| Educational Mode Rejection | Voucher date is on an unsupported day (e.g. 15th of the month). | In Tally Educational mode, dates are restricted to **1st, 2nd, or 31st** of any month. |


