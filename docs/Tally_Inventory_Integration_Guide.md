# TallyPrime API — Complete Inventory Masters Integration Guide (Stock Items, Stock Groups, Categories, Units, Godowns & Price Lists)

This guide is the complete technical reference for all **Inventory Master Operations** in TallyPrime (Versions 1.0 through 5.0). It documents exact official XML envelope structures, field hierarchies, multi-godown opening balance allocations, standard cost/selling price matrices, GST/HSN rate setups, alternate/compound unit conversions, and ready-to-run cURL/XML commands for **Create**, **Alter**, **Delete**, and **Pull** operations with **live verified Tally responses**.

---

## Table of Contents
1. [Core Architecture & Inventory Object Model](#1-core-architecture--inventory-object-model)
2. [Master Field Specifications & Tag Hierarchy](#2-master-field-specifications--tag-hierarchy)
3. [Part I: Stock Item Operations (`<STOCKITEM>`)](#3-part-i-stock-item-operations-stockitem)
   - [About Stock Item & Hierarchy](#about-stock-item)
   - [Stock Item Tag Specifications (XML & JSON)](#stock-item-tag-specification)
   - [Batch Allocations Specification](#4-batch-allocation-tags-batchallocationslist)
   - [Format Comparison: Full Stock Item Schema (Coffee Beans)](#format-comparison-full-stock-item-schema-with-batches--alternate-units)
   - [Item 1: Create Standard Stock Item with GST & HSN Details](#item-1-create-standard-stock-item-with-gst--hsn-details)
   - [Item 2: Create Stock Item with Opening Balance & Multi-Godown Allocations](#item-2-create-stock-item-with-opening-balance--multi-godown-allocations)
   - [Item 3: Create Stock Item with Standard Cost & Selling Price Lists](#item-3-create-stock-item-with-standard-cost--selling-price-lists)
   - [Item 4: Alter a Stock Item (Description, HSN, Base Units)](#item-4-alter-a-stock-item)
   - [Item 5: Delete a Stock Item](#item-5-delete-a-stock-item)
   - [Item 6: Pull Single Stock Item with Full Details (Object Export)](#item-6-pull-single-stock-item-with-full-details)
   - [Item 7: Pull All Stock Items (TDL Collection with Balances & Valuation)](#item-7-pull-all-stock-items)
   - [Item 8: Pull Stock Items Filtered by Stock Group (`CHILDOF`)](#item-8-pull-stock-items-filtered-by-stock-group)
4. [Part II: Stock Group Operations (`<STOCKGROUP>`)](#4-part-ii-stock-group-operations-stockgroup)
   - [About Stock Group & Hierarchy](#about-stock-group)
   - [Stock Group Tag Specifications (XML & JSON)](#stock-group-tag-specification)
   - [Group 1: Create Stock Group (Tea Products & Instant Beverages)](#group-1-create-stock-group)
   - [Group 2: Create Sub-Stock Group under Parent Group](#group-2-create-sub-stock-group-under-parent-group)
   - [Group 3: Alter Stock Group (Enable ISADDABLE)](#group-3-alter-stock-group-enable-isaddable)
   - [Group 4: Delete Stock Group (Tea Products & Instant Beverages)](#group-4-delete-stock-group)
   - [Group 5: Pull Single Stock Group (Laptops & Gadgets)](#group-5-pull-single-stock-group-object-export)
   - [Group 6: Pull All Stock Groups (Built-in Collection)](#group-6-pull-all-stock-groups-built-in--tdl-collection)
   - [Group 7: Pull Stock Groups with Zero Closing Balance Filter](#group-7-pull-stock-groups-with-zero-closing-balance-filter)
   - [Group 8: Pull Stock Groups with Non-Zero Closing Balance Filter](#group-8-pull-stock-groups-with-non-zero-closing-balance-filter)
5. [Part III: Stock Category Operations (`<STOCKCATEGORY>`)](#5-part-iii-stock-category-operations-stockcategory)
   - [Category 1: Create Stock Category](#category-1-create-stock-category)
   - [Category 2: Pull All Stock Categories (TDL Collection)](#category-2-pull-all-stock-categories)
6. [Part IV: Unit of Measure Operations (`<UNIT>`)](#6-part-iv-unit-of-measure-operations-unit)
   - [About Units (Simple vs Compound)](#about-units-unit-of-measure)
   - [Unit Master Tag Specifications (XML & JSON)](#unit-master-tag-specification)
   - [Format Comparison: Simple vs Compound Units](#format-comparison-simple-vs-compound-units)
   - [Unit 1: Create Simple Unit (Box, BAG, Tons)](#unit-1-create-simple-unit)
   - [Unit 2: Create Compound Unit (Kg of 1000 gm & 1 BAG = 100 Pkt)](#unit-2-create-compound-unit)
   - [Unit 3: Alter a Unit (Set Decimal Places)](#unit-3-alter-a-unit-set-decimal-places)
   - [Unit 4: Delete a Unit (Tons)](#unit-4-delete-a-unit-of-measure)
   - [Unit 5: Pull Single Unit Object (Nos & Pkt)](#unit-5-pull-single-unit-object-object-export)
   - [Unit 6: Pull All Simple Units Only (TDL Formula Filter)](#unit-6-pull-all-simple-units-only-tdl-formula-filter)
7. [Part V: Godown / Location Operations (`<GODOWN>`)](#7-part-v-godown--location-operations-godown)
   - [Godown 1: Create Godown with Address & Pincode](#godown-1-create-godown-with-address--pincode)
   - [Godown 2: Pull All Godowns (TDL Collection)](#godown-4-pull-all-godowns)
8. [Part VI: Price List & Price Level Matrix](#8-part-vi-price-list--price-level-matrix)
   - [Price 1: Create Price Level Master](#price-1-create-price-level-master)
   - [Price 2: Configure Price List with Quantity Slabs & Discount %](#price-2-configure-price-list-with-quantity-slabs--discount-)
9. [Part VII: Best Practices & Error Handling](#9-part-vii-best-practices--error-handling)
10. [Part VIII: Common Tally XML Exceptions, Root Causes & Fixes](#10-part-viii-common-tally-xml-exceptions-root-causes--fixes)

---

## 1. Core Architecture & Inventory Object Model

In TallyPrime, inventory tracking is built on five core master primitives structured hierarchically:

```
                  ┌──────────────────────┐
                  │   STOCK CATEGORY     │ (e.g. Electronics, Furniture)
                  └──────────┬───────────┘
                             │
 ┌────────────────┐          │          ┌────────────────┐
 │  STOCK GROUP   ├──────────┼──────────┤   STOCK ITEM   │
 │ (Parent Group) │          │          │ (SKU / Product)│
 └────────────────┘          │          └───────┬────────┘
                             │                  │
                             │          ┌───────┴────────┐
                             │          │     UNITS      │ (Simple / Compound)
                             │          │   (Nos, Box)   │
                             │          └────────────────┘
                             │
                  ┌──────────┴───────────┐
                  │  GODOWN / WAREHOUSE  │ (Location / Batch Allocation)
                  │ (Central Warehouse)  │
                  └──────────────────────┘
```

### Communication Protocol
- **Endpoint**: `http://<host>:<port>/` (Default: `http://localhost:9000/`)
- **HTTP Method**: `POST`
- **Headers**: `Content-Type: text/xml`
- **Envelope Format**: Standard Tally `<ENVELOPE>` containing `<HEADER>` and `<BODY>` with `<TALLYMESSAGE xmlns:UDF="TallyUDF">`.

---

## 2. Master Field Specifications & Tag Hierarchy

| Master Entity | Primary XML Tag | Key Attributes & Children | Function in Tally |
| :--- | :--- | :--- | :--- |
| **Stock Item** | `<STOCKITEM>` | `NAME`, `PARENT`, `CATEGORY`, `BASEUNITS`, `ADDITIONALUNITS`, `GSTDETAILS.LIST`, `BATCHALLOCATIONS.LIST`, `STANDARDCOSTLIST.LIST`, `STANDARDPRICELIST.LIST` | Represents the sellable/purchasable product SKU. |
| **Stock Group** | `<STOCKGROUP>` | `NAME`, `PARENT`, `ISADDABLE` | Groups similar products together for reporting and valuation. |
| **Stock Category** | `<STOCKCATEGORY>` | `NAME`, `PARENT` | Multi-dimensional categorization orthogonal to stock groups. |
| **Unit of Measure** | `<UNIT>` | `NAME`, `ISSIMPLEUNIT`, `DECIMALPLACES`, `ORIGINALNAME`, `UQCDETAILS.LIST`, `CONVERSION`, `BASEUNITS`, `ADDITIONALUNITS` | Measurement unit for quantities and rates. |
| **Godown** | `<GODOWN>` | `NAME`, `PARENT`, `ADDRESS.LIST`, `PINCODE` | Physical warehouse, store, or storage bin location. |
| **Price List** | `<PRICELIST.LIST>` | `PRICELEVEL`, `APPLICABLEFROM`, `FROMQTY`, `TOQTY`, `RATE`, `DISCOUNT` | Tiered volume pricing matrix per price level. |

---

## 3. Part I: Stock Item Operations (`<STOCKITEM>`)

### About Stock Item
A **Stock Item** is a master that represents an individual product or material that a business buys, sells, or stores in inventory. It is the core inventory tracking unit in TallyPrime for quantity, value, batch aging, and GST rate determination.

Each stock item maintains key properties:
- **Name**: Unique identifier for the product SKU.
- **Base Unit of Measure**: Primary unit in which quantities and rates are expressed (e.g. `Kg`, `nos`, `Box`).
- **Stock Group & Category**: Classification for financial reporting and parallel grouping.
- **Opening Balance**: Initial stock quantity, rate, and valuation allocated across warehouses.
- **Batch Details**: Tracking manufacturing date, expiry date, and batch identifiers.

#### Product Hierarchy Example
```
Electronics (Stock Group)
├── iPhone 14 (Stock Item)
├── Samsung Galaxy S23 (Stock Item)
└── Dell Laptop (Stock Item)
```

#### Integration Use Cases
- **Synchronize Product Catalogs**: Map external ERP / E-commerce SKUs directly into Tally inventory masters.
- **Record Inventory Transactions**: Power item-level line entries in Sales, Purchases, Credit Notes, and Stock Journals.
- **Enable Automated Inventory Updates**: Automatically maintain real-time closing balances, reorder thresholds, and valuations.

---

### Stock Item Tag Specification

#### 1. Applicable for XML Format
| Tag / Attribute | Identifier | Mandatory | Data Type | Explanation |
| :--- | :--- | :---: | :--- | :--- |
| `STOCKITEM` | Tag | **Yes** | String | Specifies the object type (`<STOCKITEM>`). |
| `NAME` | Attribute of `STOCKITEM` | **Yes** | String | The name of the Stock Item. Uniquely identifies the item within the company. |
| `NAME` | Child Tag | **Yes** | String | Primary identifying name of the stock item. |

#### 2. Applicable for JSON Format
| Key | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `metadata` | **Yes** | Object | Metadata envelope specifying object type and name. |
| `type` | **Yes** | String | Object type: `"Stock Item"`. |
| `name` | **Yes** | String | Unique name of the Stock Item within the company. |

#### 3. Core Field Specification (XML & JSON)
| Tag | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `NAME` | **Yes** | String | Name of the stock item. |
| `BASEUNITS` | **Recommended** | String | Base unit of measure (e.g. `Kg`, `nos`, `Box`). Crucial for quantity tracking and stock updates. |
| `PARENT` | No | String | Stock Group to which the item belongs. In absence, Tally assigns `'Primary'`. |
| `CATEGORY` | No | String | Stock Category for parallel classification. In absence, Tally assigns `&#4; Not Applicable`. |
| `ADDITIONALUNITS` | No | String | Alternate / secondary unit of measure for multi-unit tracking. |
| `CONVERSION` | Yes (Conditional) | Number | Required when `ADDITIONALUNITS` is specified. Conversion factor from additional unit to base unit. |
| `DENOMINATOR` | Yes (Conditional) | Number | Required when `ADDITIONALUNITS` is specified. Denominator factor for conversion math. |
| `OPENINGBALANCE` | No | Quantity | Opening quantity for the item (e.g. `200 Kg`, `50 nos`). |
| `OPENINGRATE` | No | Rate | Opening unit rate (e.g. `400.00/Kg`, `500.00/nos`). |
| `OPENINGVALUE` | No | Amount | Opening valuation. **Must be negative for Debit/Asset stock** (e.g. `-80000.00`). |
| `ISBATCHWISEON` | No | Logical (`Yes`/`No`) | Enables batch-wise allocations and tracking. Default is `No`. |

#### 4. Batch Allocation Tags (`<BATCHALLOCATIONS.LIST>`)
When `ISBATCHWISEON` is enabled, the following tags allocate opening stock to specific batches and godowns:

| Tag / Collection | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `BATCHALLOCATIONS.LIST` | **Yes** (Conditional) | Collection | Container for batch-specific quantity and valuation breakdowns. |
| `GODOWNNAME` | No | String | Physical godown/warehouse. Defaults to `Main Location` if omitted. |
| `BATCHNAME` | **Yes** (Conditional) | String | Identifier for the batch (e.g. `Batch1`, `Primary Batch`). |
| `OPENINGBALANCE` | **Yes** (Conditional) | Quantity | Quantity allocated to this specific batch (e.g. `200 Kg`). |
| `OPENINGRATE` | No | Rate | Unit rate for this batch (e.g. `400.00/Kg`). |
| `OPENINGVALUE` | No | Amount | Total opening valuation for this batch (e.g. `-80000.00`). |

#### 5. System-Generated Tags (Read-Only)
| Tag | Nature | Data Type | Explanation |
| :--- | :--- | :--- | :--- |
| `GUID` | System Generated | String | Globally unique identifier generated by Tally for the stock item. |
| `ALTERID` | System Generated | Number | Version counter incremented upon every modification. |
| `OBJECTUPDATEACTION` | System Generated | String | Last operation performed (`Create`, `Alter`, `Delete`). |

---

### Format Comparison: Full Stock Item Schema with Batches & Alternate Units

#### XML Format — Full Stock Item (`Coffee Beans`):
```xml
<STOCKITEM NAME="Coffee Beans" ACTION="Create">
  <NAME>Coffee Beans</NAME>
  <PARENT>Coffee</PARENT>
  <CATEGORY>Raw Materials</CATEGORY>
  <BASEUNITS>Kg</BASEUNITS>
  <ADDITIONALUNITS>gm</ADDITIONALUNITS>
  <CONVERSION>1</CONVERSION>
  <DENOMINATOR>1000</DENOMINATOR>
  <ISBATCHWISEON>Yes</ISBATCHWISEON>
  <OPENINGBALANCE>200 Kg</OPENINGBALANCE>
  <OPENINGRATE>400.00/Kg</OPENINGRATE>
  <OPENINGVALUE>-80000.00</OPENINGVALUE>
  <BATCHALLOCATIONS.LIST>
    <GODOWNNAME>Main Location</GODOWNNAME>
    <BATCHNAME>Batch1</BATCHNAME>
    <OPENINGBALANCE>200 Kg</OPENINGBALANCE>
    <OPENINGRATE>400.00/Kg</OPENINGRATE>
    <OPENINGVALUE>-80000.00</OPENINGVALUE>
  </BATCHALLOCATIONS.LIST>
</STOCKITEM>
```

#### JSON Format — Full Stock Item (`Coffee Beans`):
```json
{
  "metadata": {
    "type": "Stock Item",
    "name": "Coffee Beans"
  },
  "name": "Coffee Beans",
  "parent": "Coffee",
  "category": "Raw Materials",
  "baseunits": "Kg",
  "additionalunits": "gm",
  "conversion": "1",
  "denominator": "1000",
  "isbatchwiseon": true,
  "openingbalance": "200 Kg",
  "openingrate": "400.00/Kg",
  "openingvalue": "-80000.00",
  "batchallocations": [
    {
      "godownname": "Main Location",
      "batchname": "Batch1",
      "openingbalance": "200 Kg",
      "openingrate": "400.00/Kg",
      "openingvalue": "-80000.00"
    }
  ]
}
```

---

### Item 1: Create Stock Item

#### Example 1: Create Stock Item 'Tea Powder'
Creates standard stock item `Tea Powder` under primary stock group with base units `nos`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="Tea Powder" Action="Create">
                    <NAME>Tea Powder</NAME>
                    <PARENT>&#4; Primary</PARENT>
                    <BASEUNITS>nos</BASEUNITS>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>41</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Create Stock Item 'NoteBooks'
Creates standard stock item `NoteBooks` with base units `nos`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="NoteBooks" Action="Create">
                    <NAME>NoteBooks</NAME>
                    <PARENT>&#4; Primary</PARENT>
                    <BASEUNITS>nos</BASEUNITS>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>42</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 3: Create Stock Item 'Ink Pens' with Opening Balance (200 nos)
Creates stock item `Ink Pens` with an initial opening balance quantity of 200 nos.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="Ink Pens" Action="Create">
                    <NAME>Ink Pens</NAME>
                    <PARENT>&#4; Primary</PARENT>
                    <BASEUNITS>nos</BASEUNITS>
                    <OPENINGBALANCE>200 nos</OPENINGBALANCE>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>43</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 4: Create Stock Item with 18% GST (CGST & SGST) & HSN Code 8471
Creates advanced item `Dell OptiPlex Desktop` with full GST rate matrix (9% CGST + 9% SGST / 18% IGST) and HSN `8471`.

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="Dell OptiPlex Desktop" ACTION="Create">
          <NAME>Dell OptiPlex Desktop</NAME>
          <PARENT>Electronics</PARENT>
          <CATEGORY>Hardware</CATEGORY>
          <BASEUNITS>nos</BASEUNITS>
          <GSTAPPLICABLE>Applicable</GSTAPPLICABLE>
          <GSTTYPEOFSUPPLY>Goods</GSTTYPEOFSUPPLY>
          <HSNCODE>8471</HSNCODE>
          <GSTDETAILS.LIST>
            <APPLICABLEFROM>20250401</APPLICABLEFROM>
            <TAXABILITY>Taxable</TAXABILITY>
            <HSNCODE>8471</HSNCODE>
            <STATEWISEDETAILS.LIST>
              <STATENAME>Any</STATENAME>
              <RATEDETAILS.LIST>
                <GSTRATEDUTYHEAD>IGST</GSTRATEDUTYHEAD>
                <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                <GSTRATEDETAIL>18.00</GSTRATEDETAIL>
              </RATEDETAILS.LIST>
              <RATEDETAILS.LIST>
                <GSTRATEDUTYHEAD>CGST</GSTRATEDUTYHEAD>
                <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                <GSTRATEDETAIL>9.00</GSTRATEDETAIL>
              </RATEDETAILS.LIST>
              <RATEDETAILS.LIST>
                <GSTRATEDUTYHEAD>SGST/UTGST</GSTRATEDUTYHEAD>
                <GSTRATEVALUATIONTYPE>Based on Value</GSTRATEVALUATIONTYPE>
                <GSTRATEDETAIL>9.00</GSTRATEDETAIL>
              </RATEDETAILS.LIST>
            </STATEWISEDETAILS.LIST>
          </GSTDETAILS.LIST>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>49</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Item 2: Create Stock Item with Opening Balance & Multi-Godown Allocations
Creates an item with an initial opening balance of 50 Nos @ ₹500/Nos = ₹25,000 allocated to a specific Godown (`Central Warehouse`).

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="Wireless Mouse M185" ACTION="Create">
          <NAME>Wireless Mouse M185</NAME>
          <PARENT>Electronics</PARENT>
          <CATEGORY>Hardware</CATEGORY>
          <BASEUNITS>nos</BASEUNITS>
          <OPENINGBALANCE>50 nos</OPENINGBALANCE>
          <OPENINGRATE>500.00/nos</OPENINGRATE>
          <OPENINGVALUE>-25000.00</OPENINGVALUE>
          <BATCHALLOCATIONS.LIST>
            <GODOWNNAME>Central Warehouse</GODOWNNAME>
            <BATCHNAME>Primary Batch</BATCHNAME>
            <OPENINGBALANCE>50 nos</OPENINGBALANCE>
            <OPENINGRATE>500.00/nos</OPENINGRATE>
            <OPENINGVALUE>-25000.00</OPENINGVALUE>
          </BATCHALLOCATIONS.LIST>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>28</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>33</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
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

### Item 3: Create Stock Item with Standard Cost & Selling Price Lists
Pre-configures the standard purchase cost (₹1,800) and standard selling price (₹2,500) effective from 01-Apr-2025.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="Mechanical Keyboard RGB" ACTION="Create">
          <NAME>Mechanical Keyboard RGB</NAME>
          <PARENT>Electronics</PARENT>
          <BASEUNITS>nos</BASEUNITS>
          <STANDARDCOSTLIST.LIST>
            <DATE>20250401</DATE>
            <RATE>1800.00/nos</RATE>
          </STANDARDCOSTLIST.LIST>
          <STANDARDPRICELIST.LIST>
            <DATE>20250401</DATE>
            <RATE>2500.00/nos</RATE>
          </STANDARDPRICELIST.LIST>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>28</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>34</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
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

### Item 4: Alter a Stock Item

#### Example 1: Alter Stock Item 'Tea Powder' (Set Opening Balance 200 NOS)
Updates opening quantity balance of `Tea Powder` to 200 NOS.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="Tea Powder" Action="Alter">
                    <NAME>Tea Powder</NAME>
                    <OPENINGBALANCE>200 NOS</OPENINGBALANCE>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>44</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Alter Stock Item 'NoteBooks' (Set Opening Balance 100 NOS)
Updates opening quantity balance of `NoteBooks` to 100 NOS.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="NoteBooks" Action="Alter">
                    <NAME>NoteBooks</NAME>
                    <OPENINGBALANCE>100 NOS</OPENINGBALANCE>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>45</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 3: Alter Stock Item 'Ink Pens' (Enable Batch Allocations with 2 Batches)
Enables `<ISBATCHWISEON>Yes</ISBATCHWISEON>` on `Ink Pens` and allocates opening stock across two distinct batches:
- **Batch 1**: `Main Location`, `Batch1`, 100 nos @ ₹10.00/nos = ₹1,000.00 (`-1000.00`)
- **Batch 2**: `Main Location`, `Batch2`, 100 nos @ ₹15.00/nos = ₹1,500.00 (`-1500.00`)

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="Ink Pens" Action="Alter">
                    <NAME>Ink Pens</NAME>
                    <ISBATCHWISEON>Yes</ISBATCHWISEON>
                    <BATCHALLOCATIONS.LIST>
                        <GODOWNNAME>Main Location</GODOWNNAME>
                        <BATCHNAME>Batch1</BATCHNAME>
                        <OPENINGBALANCE>100 nos</OPENINGBALANCE>
                        <OPENINGVALUE>-1000.00</OPENINGVALUE>
                        <OPENINGRATE>10.00/nos</OPENINGRATE>
                    </BATCHALLOCATIONS.LIST>
                    <BATCHALLOCATIONS.LIST>
                        <GODOWNNAME>Main Location</GODOWNNAME>
                        <BATCHNAME>Batch2</BATCHNAME>
                        <OPENINGBALANCE>100 nos</OPENINGBALANCE>
                        <OPENINGVALUE>-1500.00</OPENINGVALUE>
                        <OPENINGRATE>15.00/nos</OPENINGRATE>
                    </BATCHALLOCATIONS.LIST>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>46</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 4: Alter Description & Narration ('Dell OptiPlex Desktop')
Updates item specs, description, and audit narration.

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="Dell OptiPlex Desktop" ACTION="Alter">
          <NAME>Dell OptiPlex Desktop</NAME>
          <DESCRIPTION>Desktop Computer i7 16GB 512GB SSD</DESCRIPTION>
          <NARRATION>Updated computer specs</NARRATION>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>50</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Item 5: Delete a Stock Item
Permanently deletes a stock item from Tally.

> [!IMPORTANT]
> **Stock Item Deletion Rule**: In TallyPrime, a Stock Item can only be deleted if it is not referenced by any accounting or inventory vouchers (Sales, Purchases, Delivery Notes, Stock Journals) or price lists.

#### Example 1: Delete Stock Item 'Tea Powder'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="Tea Powder" Action="Delete">
                    <NAME>Tea Powder</NAME>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>47</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Delete Stock Item 'NoteBooks'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKITEM NAME="NoteBooks" Action="Delete">
                    <NAME>NoteBooks</NAME>
                </STOCKITEM>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Item 6: Pull Single Stock Item with Full Details (Object Export)
Fetches specific fields or the entire object structure for an individual stock item using `<TYPE>Object</TYPE>`.

#### Example 1: Pull Stock Item 'Coffee Powder' (Name, Parent, BaseUnits, Closing Balance)
Retrieves core attributes and live closing stock for `Coffee Powder`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Item</SUBTYPE>
        <ID TYPE="Name">Coffee Powder</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>BaseUnits</FETCH>
                <FETCH>ClosingBalance</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <STOCKITEM NAME="Coffee Powder" RESERVEDNAME="" ID="307" REQNAME="Coffee Powder">
     <PARENT TYPE="String">Coffee</PARENT>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ADDITIONALUNITS TYPE="String">&#4; Not Applicable</ADDITIONALUNITS>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 307</MASTERID>
     <DENOMINATOR TYPE="Number"> 1</DENOMINATOR>
     <CONVERSION TYPE="Number">0</CONVERSION>
     <CLOSINGBALANCE TYPE="Quantity"> 200 nos</CLOSINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee Powder</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 2: Pull Only Closing Balance of 'Apple MacBook Pro Laptop'
Lightweight object query requesting only the closing inventory balance.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Item</SUBTYPE>
        <ID TYPE="Name">Apple MacBook Pro Laptop</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>ClosingBalance</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="" ID="223" REQNAME="Apple MacBook Pro Laptop">
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ADDITIONALUNITS TYPE="String">&#4; Not Applicable</ADDITIONALUNITS>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 223</MASTERID>
     <DENOMINATOR TYPE="Number"> 1</DENOMINATOR>
     <CONVERSION TYPE="Number">0</CONVERSION>
     <CLOSINGBALANCE TYPE="Quantity">-23 nos</CLOSINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Apple MacBook Pro Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 3: Pull Complete Stock Item Schema ('Dell OptiPlex Desktop')
Fetches full object properties including multi-godown batches, standard costs, and GST rate schedules using wildcard `<FETCH>*</FETCH>`.

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Object</TYPE>
    <SUBTYPE>Stock Item</SUBTYPE>
    <ID TYPE="Name">Dell OptiPlex Desktop</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
      <FETCHLIST>
        <FETCH>*</FETCH>
      </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>50</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <STOCKITEM NAME="Dell OptiPlex Desktop" RESERVEDNAME="" ID="512" REQNAME="Dell OptiPlex Desktop">
     <ACTIVEFROM TYPE="Date"></ACTIVEFROM>
     <ACTIVETO TYPE="Date"></ACTIVETO>
     <PRICELEVELDATE TYPE="Date"></PRICELEVELDATE>
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000200</GUID>
     <PRICELEVEL TYPE="String"></PRICELEVEL>
     <PARENT TYPE="String">Electronics</PARENT>
     <CATEGORY TYPE="String">Hardware</CATEGORY>
     <NARRATION TYPE="String">Updated computer specs</NARRATION>
     <REMOTEGUID TYPE="String"></REMOTEGUID>
     <REMOTEALTGUID TYPE="String"></REMOTEALTGUID>
     <ENTEREDBY TYPE="String"></ENTEREDBY>
     <ALTEREDBY TYPE="String"></ALTEREDBY>
     <TYPEOFUPDATEACTIVITY TYPE="String">HttpRequest</TYPEOFUPDATEACTIVITY>
     <OBJECTUPDATEACTION TYPE="String">Alter</OBJECTUPDATEACTION>
     <REQUESTORRULE TYPE="String"></REQUESTORRULE>
     <TDSAPPLICABLE TYPE="String"></TDSAPPLICABLE>
     <TCSAPPLICABLE TYPE="String"></TCSAPPLICABLE>
     <GSTAPPLICABLE TYPE="String"></GSTAPPLICABLE>
     <TAXCLASSIFICATIONNAME TYPE="String">&#4; Not Applicable</TAXCLASSIFICATIONNAME>
     <DESCRIPTION TYPE="String">Desktop Computer i7 16GB 512GB SSD</DESCRIPTION>
     <GSTTYPEOFSUPPLY TYPE="String">Goods</GSTTYPEOFSUPPLY>
     <SERVICETAXAPPLICABLE TYPE="String"></SERVICETAXAPPLICABLE>
     <EXCISEAPPLICABILITY TYPE="String"></EXCISEAPPLICABILITY>
     <SALESTAXCESSAPPLICABLE TYPE="String"></SALESTAXCESSAPPLICABLE>
     <VATAPPLICABLE TYPE="String"></VATAPPLICABLE>
     <LEDGERNAME TYPE="String"></LEDGERNAME>
     <COSTINGMETHOD TYPE="String">Default</COSTINGMETHOD>
     <VALUATIONMETHOD TYPE="String">Default</VALUATIONMETHOD>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ADDITIONALUNITS TYPE="String">&#4; Not Applicable</ADDITIONALUNITS>
     <EXCISETAXTYPE TYPE="String"></EXCISETAXTYPE>
     <NATUREOFITEM TYPE="String"></NATUREOFITEM>
     <EXCISEITEMCLASSIFICATION TYPE="String"></EXCISEITEMCLASSIFICATION>
     <OLDBASICTARIFFTYPE TYPE="String"></OLDBASICTARIFFTYPE>
     <TCSCATEGORY TYPE="String"></TCSCATEGORY>
     <BASICTARIFFTYPE TYPE="String"></BASICTARIFFTYPE>
     <VATCOMMODITY TYPE="String"></VATCOMMODITY>
     <ENTRYTAXCOMMODITY TYPE="String"></ENTRYTAXCOMMODITY>
     <VATBASEUNIT TYPE="String"></VATBASEUNIT>
     <VATTRAILUNIT TYPE="String"></VATTRAILUNIT>
     <VATSCHDLENTRTYNO TYPE="String"></VATSCHDLENTRTYNO>
     <REORDERPERIOD TYPE="String"></REORDERPERIOD>
     <REORDERROUNDTYPE TYPE="String"></REORDERROUNDTYPE>
     <MINORDERPERIOD TYPE="String"></MINORDERPERIOD>
     <MINORDERROUNDTYPE TYPE="String"></MINORDERROUNDTYPE>
     <GSTREPUOM TYPE="String"></GSTREPUOM>
     <GSTCONVUNIT TYPE="String"></GSTCONVUNIT>
     <ISCOSTCENTRESON TYPE="Logical">No</ISCOSTCENTRESON>
     <ISBATCHWISEON TYPE="Logical">No</ISBATCHWISEON>
     <ISPERISHABLEON TYPE="Logical">No</ISPERISHABLEON>
     <ISENTRYTAXAPPLICABLE TYPE="Logical"></ISENTRYTAXAPPLICABLE>
     <ISCOSTTRACKINGON TYPE="Logical">No</ISCOSTTRACKINGON>
     <ISMSTFROMSYNC TYPE="Logical"></ISMSTFROMSYNC>
     <ISUPDATINGTARGETID TYPE="Logical"></ISUPDATINGTARGETID>
     <ISDELETED TYPE="Logical"></ISDELETED>
     <ISSECURITYONWHENENTERED TYPE="Logical"></ISSECURITYONWHENENTERED>
     <ASORIGINAL TYPE="Logical">No</ASORIGINAL>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <ISRATEINCLUSIVEVAT TYPE="Logical"></ISRATEINCLUSIVEVAT>
     <CANDELETE TYPE="Logical">Yes</CANDELETE>
     <IGNOREPHYSICALDIFFERENCE TYPE="Logical">No</IGNOREPHYSICALDIFFERENCE>
     <IGNORENEGATIVESTOCK TYPE="Logical">No</IGNORENEGATIVESTOCK>
     <TREATSALESASMANUFACTURED TYPE="Logical">No</TREATSALESASMANUFACTURED>
     <TREATPURCHASESASCONSUMED TYPE="Logical">No</TREATPURCHASESASCONSUMED>
     <TREATREJECTSASSCRAP TYPE="Logical">No</TREATREJECTSASSCRAP>
     <HASMFGDATE TYPE="Logical">No</HASMFGDATE>
     <ALLOWUSEOFEXPIREDITEMS TYPE="Logical">No</ALLOWUSEOFEXPIREDITEMS>
     <IGNOREBATCHES TYPE="Logical">No</IGNOREBATCHES>
     <IGNOREGODOWNS TYPE="Logical">No</IGNOREGODOWNS>
     <ADJDIFFINFIRSTSALELEDGER TYPE="Logical"></ADJDIFFINFIRSTSALELEDGER>
     <ADJDIFFINFIRSTPURCLEDGER TYPE="Logical"></ADJDIFFINFIRSTPURCLEDGER>
     <CALCONMRP TYPE="Logical">No</CALCONMRP>
     <EXCLUDEJRNLFORVALUATION TYPE="Logical"></EXCLUDEJRNLFORVALUATION>
     <ISMRPINCLOFTAX TYPE="Logical">No</ISMRPINCLOFTAX>
     <ISADDLTAXEXEMPT TYPE="Logical"></ISADDLTAXEXEMPT>
     <ISSUPPLEMENTRYDUTYON TYPE="Logical"></ISSUPPLEMENTRYDUTYON>
     <GVATISEXCISEAPPL TYPE="Logical"></GVATISEXCISEAPPL>
     <ISADDITIONALTAX TYPE="Logical">No</ISADDITIONALTAX>
     <ISCESSEXEMPTED TYPE="Logical">No</ISCESSEXEMPTED>
     <REORDERASHIGHER TYPE="Logical">No</REORDERASHIGHER>
     <MINORDERASHIGHER TYPE="Logical">No</MINORDERASHIGHER>
     <ISEXCISECALCULATEONMRP TYPE="Logical"></ISEXCISECALCULATEONMRP>
     <INCLUSIVETAX TYPE="Logical"></INCLUSIVETAX>
     <GSTCALCSLABONMRP TYPE="Logical">No</GSTCALCSLABONMRP>
     <MODIFYMRPRATE TYPE="Logical">No</MODIFYMRPRATE>
     <ERRKEY TYPE="Number">0</ERRKEY>
     <ALTERID TYPE="Number"> 973</ALTERID>
     <REMOTEALTERID TYPE="Number">0</REMOTEALTERID>
     <MASTERID TYPE="Number"> 512</MASTERID>
     <DENOMINATOR TYPE="Number"> 1</DENOMINATOR>
     <CONVERSION TYPE="Number">0</CONVERSION>
     <RATEOFMRP TYPE="Number">0</RATEOFMRP>
     <BASICRATEOFEXCISE TYPE="Number">0</BASICRATEOFEXCISE>
     <RATEOFENTRYTAX TYPE="Number">0</RATEOFENTRYTAX>
     <RATEOFVAT TYPE="Number">0</RATEOFVAT>
     <RATEOFSAT TYPE="Number">0</RATEOFSAT>
     <VATBASENO TYPE="Number">0</VATBASENO>
     <VATTRAILNO TYPE="Number">0</VATTRAILNO>
     <VATACTUALRATIO TYPE="Number">0</VATACTUALRATIO>
     <REORDERPERIODLENGTH TYPE="Number">0</REORDERPERIODLENGTH>
     <REORDERROUNDLIMIT TYPE="Number">0</REORDERROUNDLIMIT>
     <MINORDERPERIODLENGTH TYPE="Number">0</MINORDERPERIODLENGTH>
     <MINORDERROUNDLIMIT TYPE="Number">0</MINORDERROUNDLIMIT>
     <GSTITEMUNITS TYPE="Number">0</GSTITEMUNITS>
     <GSTREPUNITS TYPE="Number">0</GSTREPUNITS>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <OPENINGVALUE TYPE="Amount">0.00</OPENINGVALUE>
     <BASICVALUE TYPE="Amount"></BASICVALUE>
     <BASICQTY TYPE="Quantity"></BASICQTY>
     <REORDERBASE TYPE="Quantity"></REORDERBASE>
     <MINIMUMORDERBASE TYPE="Quantity"></MINIMUMORDERBASE>
     <OPENINGRATE TYPE="Rate"></OPENINGRATE>
     <UPDATEDDATETIME TYPE="DateTime">20260815002640000</UPDATEDDATETIME>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Dell OptiPlex Desktop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number">0</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

### Item 7: Pull All Stock Items

#### Example 1: Standard Built-in Collection ('StockItem')
Executes the native built-in collection query to export all stock items with system default attributes.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>StockItem</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="512">
    <STOCKITEM NAME="amanstock" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>amanstock</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Apple MacBook Pro Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="apple test" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>apple test</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Coffee Beans" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee Beans</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Coffee Powder" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee Powder</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer1" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer2" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer2</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer 50" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer 50</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer US" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer US</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Decaf Coffee" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Decaf Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Dell OptiPlex Desktop" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Dell OptiPlex Desktop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number">0</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Epson Eco Tank L 3252 Printers" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Epson Eco Tank L 3252 Printers</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="GST Coffee" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>GST Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Hp Pavilion 14 Laptop" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hp Pavilion 14 Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Hp Smart Tank 670 Printers" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hp Smart Tank 670 Printers</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Ink Pens" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Ink Pens</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item001" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item001</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item002" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item002</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item1" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Keyboard" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Keyboard</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="KRYSTA-1100" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>KRYSTA-1100</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="LG 32MR50C Curved Monitor" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>LG 32MR50C Curved Monitor</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Logitech MX Master 3S" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Logitech MX Master 3S</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Monitor 11" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Monitor 11</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Monitor 12" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Monitor 12</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Samsung 32 inch Curved Monitor" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Samsung 32 inch Curved Monitor</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Wireless Mouse M185" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Wireless Mouse M185</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Wireless Mouse X1" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Wireless Mouse X1</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 2: TDL Collection with Explicit Balances & Valuation
Executes a high-performance TDL collection export retrieving stock items with live Closing Balances, Closing Rates, and Valuation.

```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Stock Items</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="List of Stock Items">
            <TYPE>StockItem</TYPE>
            <FETCH>NAME,PARENT,CATEGORY,BASEUNITS,OPENINGBALANCE,CLOSINGBALANCE,CLOSINGRATE,CLOSINGVALUE,HSNCODE,GUID,ALTERID</FETCH>
          </COLLECTION>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>50</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="512">
    <STOCKITEM NAME="amanstock" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001fa</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 925</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>amanstock</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000df</GUID>
     <PARENT TYPE="String">Laptops</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 244</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-23 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">3450000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">150000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Apple MacBook Pro Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="apple test" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001f5</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 920</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>apple test</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Coffee Beans" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000020d</GUID>
     <PARENT TYPE="String">Coffee</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">Kg</BASEUNITS>
     <ALTERID TYPE="Number"> 963</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 200.000 Kg = 0 gm</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 200.000 Kg = 0 gm</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-80000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">400.00/Kg</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee Beans</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Coffee Powder" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000133</GUID>
     <PARENT TYPE="String">Coffee</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 618</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 200 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 200 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-4000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">20.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee Powder</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer1" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000113</GUID>
     <PARENT TYPE="String">Gadgets</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 622</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer2" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000114</GUID>
     <PARENT TYPE="String">Gadgets</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 623</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer2</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer 50" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000010b</GUID>
     <PARENT TYPE="String">Gadgets</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 624</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer 50</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer US" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000168</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 722</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 70 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-700000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">10000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer US</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Decaf Coffee" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000146</GUID>
     <PARENT TYPE="String">Coffee</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 656</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 800 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-12000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">15.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Decaf Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Dell OptiPlex Desktop" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000200</GUID>
     <PARENT TYPE="String">Electronics</PARENT>
     <CATEGORY TYPE="String">Hardware</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 973</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Dell OptiPlex Desktop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number">0</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Epson Eco Tank L 3252 Printers" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e2</GUID>
     <PARENT TYPE="String">Printers</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 627</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-20 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">360000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">18000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Epson Eco Tank L 3252 Printers</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="GST Coffee" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000013f</GUID>
     <PARENT TYPE="String">Coffee</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 730</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-40 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 100 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">2000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">50.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>GST Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Hp Pavilion 14 Laptop" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e0</GUID>
     <PARENT TYPE="String">Laptops</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 626</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-11 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">990000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">90000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hp Pavilion 14 Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Hp Smart Tank 670 Printers" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e1</GUID>
     <PARENT TYPE="String">Printers</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 246</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-11 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">275000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">25000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hp Smart Tank 670 Printers</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Ink Pens" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000210</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 969</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 200 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 200 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-2500.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">12.50/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Ink Pens</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item001" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000010c</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 409</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 350 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 350 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-70150.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">200.43/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item001</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item002" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000010d</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 410</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 300 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 300 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-60000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">200.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item002</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Item1" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-0000010f</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 412</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-100 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 300 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">20000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">200.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Item1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Keyboard" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000110</GUID>
     <PARENT TYPE="String">Gadgets</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 628</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Keyboard</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="KRYSTA-1100" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001f9</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">PCS</BASEUNITS>
     <ALTERID TYPE="Number"> 924</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>KRYSTA-1100</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="LG 32MR50C Curved Monitor" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e5</GUID>
     <PARENT TYPE="String">Monitors</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 250</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-4 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">56000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">14000.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>LG 32MR50C Curved Monitor</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Logitech MX Master 3S" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001ef</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 913</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Logitech MX Master 3S</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Monitor 11" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000111</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">&#4; Not Applicable</BASEUNITS>
     <ALTERID TYPE="Number"> 414</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Monitor 11</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Monitor 12" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000112</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">&#4; Not Applicable</BASEUNITS>
     <ALTERID TYPE="Number"> 415</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Monitor 12</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Samsung 32 inch Curved Monitor" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000000e3</GUID>
     <PARENT TYPE="String">Monitors</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 248</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity">-3 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">49500.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">16500.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Samsung 32 inch Curved Monitor</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Wireless Mouse M185" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000201</GUID>
     <PARENT TYPE="String">Electronics</PARENT>
     <CATEGORY TYPE="String">Hardware</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 941</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"> 50 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"> 50 nos</OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount">-25000.00</CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate">500.00/nos</CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Wireless Mouse M185</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Wireless Mouse X1" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001ee</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CATEGORY TYPE="String">&#4; Not Applicable</CATEGORY>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <ALTERID TYPE="Number"> 912</ALTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Wireless Mouse X1</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

### Item 8: Pull Stock Items of Stock Group (`CHILDOF`)
Filters items belonging exclusively to a specific parent Stock Group using `<CHILDOF>`.

#### Example 1: Pull Items of Group 'Gadgets' (Name, Parent, Balances, BaseUnits)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLStockOfGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPLStockOfGroup" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>StockItem</TYPE>
                        <CHILDOF>&quot;Gadgets&quot;</CHILDOF>
                        <NATIVEMETHOD>Name, Parent, ClosingBalance, ClosingValue, BaseUnits</NATIVEMETHOD>
                    </COLLECTION>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="512">
    <STOCKITEM NAME="Computer1" RESERVEDNAME="">
     <PARENT TYPE="String">Gadgets</PARENT>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer2" RESERVEDNAME="">
     <PARENT TYPE="String">Gadgets</PARENT>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer2</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Computer 50" RESERVEDNAME="">
     <PARENT TYPE="String">Gadgets</PARENT>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Computer 50</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Keyboard" RESERVEDNAME="">
     <PARENT TYPE="String">Gadgets</PARENT>
     <BASEUNITS TYPE="String">nos</BASEUNITS>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Keyboard</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 2: Pull Only Balance & Valuation for 'Gadgets' (ClosingBalance, ClosingRate, ClosingValue)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLStockOfGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPLStockOfGroup" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>StockItem</TYPE>
                        <CHILDOF>&quot;Gadgets&quot;</CHILDOF>
                        <NATIVEMETHOD>ClosingBalance, ClosingRate, ClosingValue</NATIVEMETHOD>
                    </COLLECTION>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="512">
    <STOCKITEM NAME="Computer1" RESERVEDNAME="">
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
    </STOCKITEM>
    <STOCKITEM NAME="Computer2" RESERVEDNAME="">
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
    </STOCKITEM>
    <STOCKITEM NAME="Computer 50" RESERVEDNAME="">
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
    </STOCKITEM>
    <STOCKITEM NAME="Keyboard" RESERVEDNAME="">
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <CLOSINGVALUE TYPE="Amount"></CLOSINGVALUE>
     <CLOSINGRATE TYPE="Rate"></CLOSINGRATE>
    </STOCKITEM>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 3: Pull Items of Group 'Laptops' (Name, Parent, Opening & Closing Balances)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPLStockOfGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPLStockOfGroup" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>StockItem</TYPE>
                        <CHILDOF>&quot;Laptops&quot;</CHILDOF>
                        <NATIVEMETHOD>Name, Parent, OpeningBalance, ClosingBalance</NATIVEMETHOD>
                    </COLLECTION>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>48</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="512">
    <STOCKITEM NAME="Apple MacBook Pro Laptop" RESERVEDNAME="">
     <PARENT TYPE="String">Laptops</PARENT>
     <CLOSINGBALANCE TYPE="Quantity">-23 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Apple MacBook Pro Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
    <STOCKITEM NAME="Hp Pavilion 14 Laptop" RESERVEDNAME="">
     <PARENT TYPE="String">Laptops</PARENT>
     <CLOSINGBALANCE TYPE="Quantity">-11 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hp Pavilion 14 Laptop</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKITEM>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

## 4. Part II: Stock Group Operations (`<STOCKGROUP>`)

### About Stock Group
In TallyPrime, a **Stock Group** is a master used to categorize stock items that share similar characteristics. It helps organize stock items and generate inventory reports by Group.

Instead of listing all products individually, businesses group them into logical groups. Stock groups can also have parent and sub-groups.

#### Product Hierarchy Example
```
Clothing (Main Stock group)
├── Shirts (Sub stock group)
│   └── Black Formal Shirt (Stock item)
├── Jeans (Sub stock group)
│   └── Blue Denim Jeans (Stock item)
└── Jackets (Sub stock group)
    └── Leather Jacket (Stock item)
```

#### Integration Use Cases
- **Maintain Product Categorization**: Aligns Tally's catalog with external ERP / E-commerce product taxonomies.
- **Enable Group-Wise Inventory Reports**: Allows fast valuation and stock summary generation at the parent group level.
- **Maintain Consistency Between Systems**: Ensures SKU classifications stay synchronized across distributed platforms.

---

### Stock Group Tag Specification

#### 1. Applicable for XML Format
| Tag / Attribute | Identifier | Mandatory | Data Type | Explanation |
| :--- | :--- | :---: | :--- | :--- |
| `STOCKGROUP` | Tag | **Yes** | String | Specifies the object type (`<STOCKGROUP>`). |
| `NAME` | Attribute of `STOCKGROUP` | **Yes** | String | The name of the Stock Group. Uniquely identifies the group within the company. |
| `NAME` | Child Tag | **Yes** | String | Primary identifying name of the Stock Group. |

#### 2. Applicable for JSON Format
| Key | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `metadata` | **Yes** | Object | Metadata envelope specifying object type and name. |
| `type` | **Yes** | String | Object type: `"Stock Group"`. |
| `name` | **Yes** | String | Unique name of the Stock Group within the company. |

#### 3. Frequently Used Tags (XML & JSON)
| Tag | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `PARENT` | No | String | Specifies the Parent Stock Group to which this group belongs. In the **absence** of this tag (or when set to `&#4; Primary`), Tally automatically sets `'Primary'` as the parent. |
| `ISADDABLE` | No | Logical (`Yes`/`No`) | Specifies if child stock items can be added. When enabled (`Yes`), Tally aggregates the total closing quantities and values of all child items if they share the same units of measure. Default is `Yes`. |

#### 4. System-Generated Tags (Read-Only)
| Tag | Nature | Data Type | Explanation |
| :--- | :--- | :--- | :--- |
| `GUID` | System Generated | String | Globally unique identifier generated by Tally for the stock group. |
| `ALTERID` | System Generated | Number | Monotonically increasing version counter used for incremental sync. |
| `OBJECTUPDATEACTION` | System Generated | String | Specifies the last operation performed (`Create`, `Alter`, `Delete`). |

---

### Group 1: Create Stock Group

#### Example 1: Create Stock Group 'Tea Products'
Creates a new top-level stock group `Tea Products`.

```bash
curl -X POST http://192.168.71.128:9000/ \
  -H "Content-Type: text/xml" \
  -d '<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Tea Products" Action="Create">
                    <NAME>Tea Products</NAME>
                    <PARENT>&#4; Primary</PARENT>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
    </BODY>
</ENVELOPE>'
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>4</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Create Stock Group 'Instant Beverages'
Creates a new stock group `Instant Beverages`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Instant Beverages" Action="Create">
                    <NAME>Instant Beverages</NAME>
                    <PARENT>&#4; Primary</PARENT>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>5</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Group 2: Create Sub-Stock Group under Parent Group
Creates a child sub-group (e.g. `Gadgets` under parent `Applications`).

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKGROUP NAME="Gadgets" ACTION="Create">
          <NAME>Gadgets</NAME>
          <PARENT>Applications</PARENT>
          <ISADDABLE>Yes</ISADDABLE>
        </STOCKGROUP>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### JSON Equivalent:
```json
{
  "metadata": {
    "type": "Stock Group",
    "name": "Gadgets"
  },
  "name": "Gadgets",
  "parent": "Applications",
  "isaddable": true
}
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>10</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>50</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Group 3: Alter Stock Group (Enable `ISADDABLE`)

#### Example 1: Alter 'Tea Products' (Set `ISADDABLE` to Yes)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Tea Products" Action="Alter">
                    <NAME>Tea Products</NAME>
                    <ISADDABLE>Yes</ISADDABLE>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>6</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Alter 'Instant Beverages' (Set `ISADDABLE` to Yes)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Instant Beverages" Action="Alter">
                    <NAME>Instant Beverages</NAME>
                    <ISADDABLE>Yes</ISADDABLE>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Group 4: Delete Stock Group

#### Example 1: Delete 'Tea Products'
Permanently removes the `Tea Products` stock group from Tally.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Tea Products" Action="Delete">
                    <NAME>Tea Products</NAME>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>8</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Delete 'Instant Beverages'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <STOCKGROUP NAME="Instant Beverages" Action="Delete">
                    <NAME>Instant Beverages</NAME>
                </STOCKGROUP>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Group 5: Pull Single Stock Group (Object Export)

#### Example 1: Pull 'Laptops' (Name, Parent, Opening & Closing Balances)
Fetches specific fields of the `Laptops` stock group using `<FETCHLIST>`.

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Group</SUBTYPE>
        <ID TYPE="Name">Laptops</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
                <FETCH>Parent</FETCH>
                <FETCH>OpeningBalance</FETCH>
                <FETCH>ClosingBalance</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <STOCKGROUP NAME="Laptops" RESERVEDNAME="" ID="219" REQNAME="Laptops">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 219</MASTERID>
     <CLOSINGBALANCE TYPE="Quantity">-34 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Laptops</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 2: Pull 'Gadgets' (Opening Balance, Closing Balance, Isaddable)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Stock Group</SUBTYPE>
        <ID TYPE="Name">Gadgets</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>OpeningBalance</FETCH>
                <FETCH>ClosingBalance</FETCH>
                <FETCH>Isaddable</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <STOCKGROUP NAME="Gadgets" RESERVEDNAME="" ID="261" REQNAME="Gadgets">
     <ISADDABLE TYPE="Logical">No</ISADDABLE>
     <ISDEEMEDPOSITIVE TYPE="Logical">Yes</ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 261</MASTERID>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Gadgets</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

### Group 6: Pull All Stock Groups (Built-in & TDL Collection)

#### Built-in Collection Query (`ID="StockGroup"`):
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>StockGroup</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
    </BODY>
</ENVELOPE>
```

##### Live TallyPrime Response (Sample Output):
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="128">
    <STOCKGROUP NAME="Applications" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Applications</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Coffee" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Electronics" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Electronics</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Finished Goods" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Finished Goods</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Gadgets" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Gadgets</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="GADGETS 1" RESERVEDNAME="">
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>GADGETS 1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Instant
... [TRUNCATED] ...
</ENVELOPE>
```

---

### Group 7: Pull Stock Groups with Zero Closing Balance Filter
Retrieves only stock groups whose `$ClosingBalance` is zero using a TDL formula filter (`$$IsEmpty:$ClosingBalance` or `$ClosingBalance = 0`).

#### XML Request:
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Stock Group ZeroBal</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPL Stock Group ZeroBal" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>StockGroup</TYPE>
                        <NATIVEMETHOD>Name, Parent, Openingbalance, ClosingBalance</NATIVEMETHOD>
                        <FILTERS>TSPL Zero Closing</FILTERS>
                    </COLLECTION>
                    <SYSTEM TYPE="Formulae" NAME="TSPL Zero Closing" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$$IsEmpty:$ClosingBalance</SYSTEM>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="128">
    <STOCKGROUP NAME="Applications" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Applications</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Coffee" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Coffee</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Electronics" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Electronics</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Finished Goods" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Finished Goods</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Gadgets" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Gadgets</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="GADGETS 1" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>GADGETS 1</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Instant Beverages" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Instant Beverages</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Tea Products" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity"></CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Tea Products</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

### Group 8: Pull Stock Groups with Non-Zero Closing Balance Filter
Retrieves stock groups that have active closing balance quantities/values.

#### XML Request:
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL Stock Group WithBal</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPL Stock Group WithBal" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>StockGroup</TYPE>
                        <NATIVEMETHOD>Name, Parent, Openingbalance, ClosingBalance</NATIVEMETHOD>
                        <FILTERS>TSPL NonZero Closing</FILTERS>
                    </COLLECTION>
                    <SYSTEM TYPE="Formulae" NAME="TSPL NonZero Closing" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">NOT $$IsEmpty:$ClosingBalance</SYSTEM>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>7</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="128">
    <STOCKGROUP NAME="Laptops" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity">-34 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Laptops</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Monitors" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity">-7 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Monitors</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
    <STOCKGROUP NAME="Printers" RESERVEDNAME="">
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <CLOSINGBALANCE TYPE="Quantity">-31 nos</CLOSINGBALANCE>
     <OPENINGBALANCE TYPE="Quantity"></OPENINGBALANCE>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Printers</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKGROUP>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

## 5. Part III: Stock Category Operations (`<STOCKCATEGORY>`)

### Category 1: Create Stock Category
Creates a new multi-dimensional stock category.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKCATEGORY NAME="Hardware" ACTION="Create">
          <NAME>Hardware</NAME>
        </STOCKCATEGORY>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>27</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>31</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
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

### Category 2: Pull All Stock Categories
Retrieves all stock categories.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Stock Categories</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="List of Stock Categories">
            <TYPE>StockCategory</TYPE>
            <FETCH>NAME,PARENT,GUID,ALTERID</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>27</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>31</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="256">
    <STOCKCATEGORY NAME="Fridge" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000100</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 396</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Fridge</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKCATEGORY>
    <STOCKCATEGORY NAME="Hardware" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000204</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 938</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Hardware</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </STOCKCATEGORY>
    <STOCKCATEGORY NAME="Mobile" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000101</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 397</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Mobile</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKCATEGORY>
    <STOCKCATEGORY NAME="TV" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000102</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 398</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>TV</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </STOCKCATEGORY>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

## 6. Part IV: Unit of Measure Operations (`<UNIT>`)

### About Units (Unit of Measure)
In TallyPrime, **Units (Unit of Measure)** are masters used to define how the quantity of stock items is measured. They determine in what measurement a stock item is stored, purchased, sold, or tracked.

#### 2 Types of Units:
1. **Simple Unit**: A single measurement unit. Example: `Nos`, `Kg`, `gm`, `Pcs`, `Box`, `BAG`, `Tons`.
2. **Compound Unit**: A combination of two units used together with a conversion multiplier. Example: `Kg of 1000 gm` (meaning 1 Kg = 1000 Grams) or `1 BAG = 100 Pkt` (1 BAG = 100 Packets).

#### Integration Sequencing Rule
> **CRITICAL RULE**: Units **MUST exist before stock items are created**. Stock items reference `<BASEUNITS>` and `<ADDITIONALUNITS>`, and Tally will fail item imports if the referenced units do not exist.

---

### Unit Master Tag Specification

#### 1. Applicable for XML Format
| Tag / Attribute | Identifier | Mandatory | Data Type | Explanation |
| :--- | :--- | :---: | :--- | :--- |
| `UNIT` | Tag | **Yes** | String | Specifies the object type (`<UNIT>`). |
| `NAME` | Attribute of `UNIT` | **Yes** | String | Symbol/identifier of the unit (e.g. `Box`, `BAG`, `Kg of 1000 gm`). |
| `NAME` | Child Tag | **Yes** | String | Primary identifying name/symbol of the unit. |

#### 2. Applicable for JSON Format
| Key | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `metadata` | **Yes** | Object | Metadata envelope specifying object type and name. |
| `type` | **Yes** | String | Object type: `"Unit"`. |
| `name` | **Yes** | String | Unique name/symbol of the unit within the company. |

#### 3. Common Configuration Tags (XML & JSON)
| Tag | Mandatory | Data Type | Explanation |
| :--- | :---: | :--- | :--- |
| `ISSIMPLEUNIT` | **Yes** | Logical (`Yes`/`No` or `true`/`false`) | `Yes` for Simple Unit; `No` for Compound Unit. |
| `BASEUNITS` | **Yes** (Conditional) | String | *Applicable only when `ISSIMPLEUNIT=No`*. Specifies base unit (e.g. `Kg`, `BAG`). |
| `ADDITIONALUNITS` | **Yes** (Conditional) | String | *Applicable only when `ISSIMPLEUNIT=No`*. Specifies sub-unit (e.g. `gm`, `Pkt`). |
| `CONVERSION` | **Yes** (Conditional) | Number | *Applicable only when `ISSIMPLEUNIT=No`*. Conversion factor (e.g. `1000`, `100`). |
| `ORIGINALNAME` | No (Conditional) | String | *Applicable only when `ISSIMPLEUNIT=Yes`*. Formal name (e.g. `Boxes`, `BAGS`, `Ton`). |
| `DECIMALPLACES` | No (Conditional) | Number | *Applicable only when `ISSIMPLEUNIT=Yes`*. Number of decimal places allowed (e.g. `2`, `3`). |

#### 4. System-Generated Tags (Read-Only)
| Tag | Nature | Data Type | Explanation |
| :--- | :--- | :--- | :--- |
| `GUID` | System Generated | String | Globally unique identifier generated by Tally for the unit. |
| `ALTERID` | System Generated | Number | Version identifier incremented upon unit modification. |
| `OBJECTUPDATEACTION` | System Generated | String | Last action performed (`Create`, `Alter`, `Delete`). |

---

### Format Comparison: Simple vs Compound Units

#### XML Format — Simple Unit (`Box`):
```xml
<UNIT NAME="Box">
  <NAME>Box</NAME>
  <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
  <ORIGINALNAME>Boxes</ORIGINALNAME>
</UNIT>
```

#### JSON Format — Simple Unit (`Box`):
```json
{
  "metadata": {
    "type": "Unit",
    "name": "Box"
  },
  "name": "Box",
  "issimpleunit": true,
  "originalname": "Boxes"
}
```

#### XML Format — Compound Unit (`Kg of 1000 gm`):
```xml
<UNIT NAME="Kg of 1000 gm">
  <NAME>Kg of 1000 gm</NAME>
  <BASEUNITS>Kg</BASEUNITS>
  <ADDITIONALUNITS>gm</ADDITIONALUNITS>
  <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
  <CONVERSION>1000</CONVERSION>
</UNIT>
```

#### JSON Format — Compound Unit (`Kg of 1000 gm`):
```json
{
  "metadata": {
    "type": "Unit",
    "name": "Kg of 1000 gm"
  },
  "name": "Kg of 1000 gm",
  "baseunits": "Kg",
  "additionalunits": "gm",
  "issimpleunit": false,
  "conversion": "1000"
}
```

---

### Unit 1: Create Simple Unit

#### Example 1: Create Unit 'Box' (Formal Name: 'Boxes')
```xml
<ENVELOPE>
   <HEADER>
      <VERSION>1</VERSION>
      <TALLYREQUEST>Import</TALLYREQUEST>
      <TYPE>Data</TYPE>
      <ID>All Masters</ID>
   </HEADER>
   <BODY>
      <DESC>
         <STATICVARIABLES>
            <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
            <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
         </STATICVARIABLES>
      </DESC>
      <DATA>
         <TALLYMESSAGE xmlns:UDF="TallyUDF">
            <UNIT NAME="Box" ACTION="Create">
               <NAME>Box</NAME>
               <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT>
               <ORIGINALNAME>Boxes</ORIGINALNAME>
            </UNIT>
         </TALLYMESSAGE>
      </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>9</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Create Unit 'BAG' (Formal Name: 'BAGS')
```xml
<ENVELOPE> 
    <HEADER> 
        <VERSION>1</VERSION> 
        <TALLYREQUEST>Import</TALLYREQUEST> 
        <TYPE>Data</TYPE> 
        <ID>All Masters</ID> 
    </HEADER> 
    <BODY> 
        <DESC> 
            <STATICVARIABLES> 
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT> 
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY> 
            </STATICVARIABLES> 
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF"> 
                <UNIT NAME="BAG" ACTION="Create"> 
                    <NAME>BAG</NAME> 
                    <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT> 
                    <ORIGINALNAME>BAGS</ORIGINALNAME> 
                </UNIT> 
            </TALLYMESSAGE> 
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>10</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 3: Create Unit 'Tons' (Formal Name: 'Ton')
```xml
<ENVELOPE> 
    <HEADER> 
        <VERSION>1</VERSION> 
        <TALLYREQUEST>Import</TALLYREQUEST> 
        <TYPE>Data</TYPE> 
        <ID>All Masters</ID> 
    </HEADER> 
    <BODY> 
        <DESC> 
            <STATICVARIABLES> 
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT> 
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY> 
            </STATICVARIABLES> 
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF"> 
                <UNIT NAME="Tons" ACTION="Create"> 
                    <NAME>Tons</NAME> 
                    <ISSIMPLEUNIT>Yes</ISSIMPLEUNIT> 
                    <ORIGINALNAME>Ton</ORIGINALNAME> 
                </UNIT> 
            </TALLYMESSAGE> 
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>11</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Unit 2: Create Compound Unit

#### Example 1: Create Compound Unit 'Kg of 1000 gm' (1 Kg = 1000 gm)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <UNIT NAME="Kg of 1000 gm" ACTION="Create">
                    <NAME>Kg of 1000 gm</NAME>
                    <BASEUNITS>Kg</BASEUNITS>
                    <ADDITIONALUNITS>gm</ADDITIONALUNITS>
                    <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
                    <CONVERSION>1000</CONVERSION>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>12</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Create Compound Unit '1 BAG = 100 Pkt'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <UNIT NAME="1 BAG = 100 Pkt" ACTION="Create">
                    <NAME>1 BAG = 100 Pkt</NAME>
                    <BASEUNITS>BAG</BASEUNITS>
                    <ADDITIONALUNITS>Pkt</ADDITIONALUNITS>
                    <ISSIMPLEUNIT>No</ISSIMPLEUNIT>
                    <CONVERSION>100</CONVERSION>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>1</CREATED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>13</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Unit 3: Alter a Unit (Set Decimal Places)

> [!NOTE]
> **Decimal Rule in Tally**: In TallyPrime, you can **increase** the number of decimal places for a unit (e.g. from 0 to 2), but Tally strictly blocks **decreasing** decimals (`<LINEERROR>Cannot Decrease Number of Decimals for 'Unit'!</LINEERROR>`) to prevent transaction truncation.

#### Example 1: Alter 'Box' (Set Decimal Places to 2)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <UNIT NAME="Box" ACTION="Alter">
                    <NAME>Box</NAME>
                    <DECIMALPLACES>2</DECIMALPLACES>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>14</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

#### Example 2: Alter 'BAG' (Set Decimal Places to 2)
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <UNIT NAME="BAG" ACTION="Alter">
                    <NAME>BAG</NAME>
                    <DECIMALPLACES>2</DECIMALPLACES>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Unit 4: Delete a Unit of Measure

#### Example 1: Delete Unit 'Tons'
Permanently deletes the unit (allowed when not referenced by any stock items or compound units).

```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Import</TALLYREQUEST>
        <TYPE>Data</TYPE>
        <ID>All Masters</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVMSTIMPORTFORMAT>XML</SVMSTIMPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
        </DESC>
        <DATA>
            <TALLYMESSAGE xmlns:UDF="TallyUDF">
                <UNIT NAME="Tons" ACTION="Delete">
                    <NAME>Tons</NAME>
                </UNIT>
            </TALLYMESSAGE>
        </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>0</ALTERED>
    <DELETED>1</DELETED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>15</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Unit 5: Pull Single Unit Object (Object Export)

#### Example 1: Pull Unit 'nos'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Unit</SUBTYPE>
        <ID TYPE="Name">nos</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>14</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <UNIT NAME="nos" RESERVEDNAME="" ID="222" REQNAME="nos">
     <NAME TYPE="String">nos</NAME>
     <ISDEEMEDPOSITIVE TYPE="Logical"></ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 222</MASTERID>
    </UNIT>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

#### Example 2: Pull Unit 'Pkt'
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Object</TYPE>
        <SUBTYPE>Unit</SUBTYPE>
        <ID TYPE="Name">Pkt</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <FETCHLIST>
                <FETCH>Name</FETCH>
            </FETCHLIST>
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
  <PRODMAJORVER>1</PRODMAJORVER>
  <PRODMINORVER>1</PRODMINORVER>
  <PRODMAJORREL>7</PRODMAJORREL>
  <PRODMINORREL>0</PRODMINORREL>
  <PRODTYPE>5</PRODTYPE>
 </HEADER>
 <BODY>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>14</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <TALLYMESSAGE>
    <UNIT NAME="Pkt" RESERVEDNAME="" ID="342" REQNAME="Pkt">
     <NAME TYPE="String">Pkt</NAME>
     <ISDEEMEDPOSITIVE TYPE="Logical"></ISDEEMEDPOSITIVE>
     <CANDELETE TYPE="Logical">No</CANDELETE>
     <MASTERID TYPE="Number"> 342</MASTERID>
    </UNIT>
   </TALLYMESSAGE>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

### Unit 6: Pull All Simple Units Only (TDL Formula Filter)
Retrieves only Simple Units using TDL filter `$IsSimpleUnit`.

#### XML Request:
```xml
<ENVELOPE>
    <HEADER>
        <VERSION>1</VERSION>
        <TALLYREQUEST>Export</TALLYREQUEST>
        <TYPE>Collection</TYPE>
        <ID>TSPL SimpleUnits</ID>
    </HEADER>
    <BODY>
        <DESC>
            <STATICVARIABLES>
                <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
                <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
            </STATICVARIABLES>
            <TDL>
                <TDLMESSAGE>
                    <COLLECTION NAME="TSPL SimpleUnits" ISMODIFY="No" ISFIXED="No" ISINITIALIZE="No" ISOPTION="No" ISINTERNAL="No">
                        <TYPE>Unit</TYPE>
                        <NATIVEMETHOD>Name, OriginalName, IsSimpleUnit</NATIVEMETHOD>
                        <FILTERS>TSPLSimpleUnitsOnly</FILTERS>
                    </COLLECTION>
                    <SYSTEM TYPE="Formulae" NAME="TSPLSimpleUnitsOnly" ISMODIFY="No" ISFIXED="No" ISINTERNAL="No">$IsSimpleUnit</SYSTEM>
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
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>9</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>39</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>14</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="4096">
    <UNIT NAME="BAG" RESERVEDNAME="">
     <NAME TYPE="String">BAG</NAME>
     <ORIGINALNAME TYPE="String">BAGS</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="BOX" RESERVEDNAME="">
     <NAME TYPE="String">BOX</NAME>
     <ORIGINALNAME TYPE="String">Boxes</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="gm" RESERVEDNAME="">
     <NAME TYPE="String">gm</NAME>
     <ORIGINALNAME TYPE="String">Grams</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="Kg" RESERVEDNAME="">
     <NAME TYPE="String">Kg</NAME>
     <ORIGINALNAME TYPE="String">Kilograms</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="nos" RESERVEDNAME="">
     <NAME TYPE="String">nos</NAME>
     <ORIGINALNAME TYPE="String">Numbers</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="PCS" RESERVEDNAME="">
     <NAME TYPE="String">PCS</NAME>
     <ORIGINALNAME TYPE="String">Pieces</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="Pkt" RESERVEDNAME="">
     <NAME TYPE="String">Pkt</NAME>
     <ORIGINALNAME TYPE="String">Packet</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="SET" RESERVEDNAME="">
     <NAME TYPE="String">SET</NAME>
     <ORIGINALNAME TYPE="String">Sets</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
    <UNIT NAME="Tons" RESERVEDNAME="">
     <NAME TYPE="String">Tons</NAME>
     <ORIGINALNAME TYPE="String">Ton</ORIGINALNAME>
     <ISSIMPLEUNIT TYPE="Logical">Yes</ISSIMPLEUNIT>
    </UNIT>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

## 7. Part V: Godown / Location Operations (`<GODOWN>`)

### Godown 1: Create Godown with Address & Pincode
Creates a physical warehouse storage location.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <GODOWN NAME="Central Warehouse" ACTION="Create">
          <NAME>Central Warehouse</NAME>
          <PARENT>&#4; Primary</PARENT>
          <PINCODE>122001</PINCODE>
        </GODOWN>
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>28</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>31</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
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

### Godown 2: Pull All Godowns
Retrieves all physical Godowns and Warehouses.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Godowns</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
      <TDL>
        <TDLMESSAGE>
          <COLLECTION NAME="List of Godowns">
            <TYPE>Godown</TYPE>
            <FETCH>NAME,PARENT,PINCODE,GUID,ALTERID</FETCH>
          </COLLECTION>
        </TDLMESSAGE>
      </TDL>
    </DESC>
  </BODY>
</ENVELOPE>
```

#### Live TallyPrime Response:
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
    <LEDGER>190</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>28</GODOWN>
    <STOCKGROUP>3</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>31</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>51</CURRENCY>
    <UNIT>4</UNIT>
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
    <TAXUNIT>92</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>93</VOUCHERNUMBERSERIES>
    <VOUCHER>84</VOUCHER>
   </CMPINFO>
  </DESC>
  <DATA>
   <COLLECTION ISMSTDEPTYPE="Yes" MSTDEPTYPE="64">
    <GODOWN NAME="Central Warehouse" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-000001ff</GUID>
     <PINCODE TYPE="String">122001</PINCODE>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 939</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Central Warehouse</NAME>
      </NAME.LIST>
     </LANGUAGENAME.LIST>
    </GODOWN>
    <GODOWN NAME="Main Location" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000063</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 403</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Main Location</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </GODOWN>
    <GODOWN NAME="Scrap house" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000107</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 404</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Scrap house</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </GODOWN>
    <GODOWN NAME="Warehouse 01" RESERVEDNAME="">
     <GUID TYPE="String">f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000108</GUID>
     <PARENT TYPE="String">&#4; Primary</PARENT>
     <ALTERID TYPE="Number"> 405</ALTERID>
     <LANGUAGENAME.LIST>
      <NAME.LIST TYPE="String">
       <NAME>Warehouse 01</NAME>
      </NAME.LIST>
      <LANGUAGEID TYPE="Number"> 1033</LANGUAGEID>
     </LANGUAGENAME.LIST>
    </GODOWN>
   </COLLECTION>
  </DATA>
 </BODY>
</ENVELOPE>

```

---

## 8. Part VI: Price List & Price Level Matrix

### Price 1: Create Price Level Master
Creates a price level identifier (e.g. `Wholesale`, `Retail`, `Dealer`).

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <PRICELEVEL.LIST>
          <NAME>Wholesale Customer</NAME>
        </PRICELEVEL.LIST>
      </TALLYMESSAGE>
    </DATA>
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
    <EXCEPTIONS>0</EXCEPTIONS>
   </IMPORTRESULT>
  </DATA>
  <DESC>
   <CMPINFO>
    <COMPANY>0</COMPANY>
    <GROUP>0</GROUP>
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>10</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>50</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

### Price 2: Configure Price List with Quantity Slabs & Discount %
Configures volume price breaks on a stock item for a price level.

#### XML Request:
```xml
<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>All Masters</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVCURRENTCOMPANY>Bhrama Enterprises</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
        <STOCKITEM NAME="Dell OptiPlex Desktop" ACTION="Alter">
          <NAME>Dell OptiPlex Desktop</NAME>
          <PRICELIST.LIST>
            <PRICELEVEL>Wholesale Customer</PRICELEVEL>
            <APPLICABLEFROM>20250401</APPLICABLEFROM>
            <PRICELEVELLIST.LIST>
              <FROMQTY>1 nos</FROMQTY>
              <TOQTY>10 nos</TOQTY>
              <RATE>45000.00/nos</RATE>
              <DISCOUNT>2.00</DISCOUNT>
            </PRICELEVELLIST.LIST>
            <PRICELEVELLIST.LIST>
              <FROMQTY>11 nos</FROMQTY>
              <TOQTY>50 nos</TOQTY>
              <RATE>42000.00/nos</RATE>
              <DISCOUNT>5.00</DISCOUNT>
            </PRICELEVELLIST.LIST>
          </PRICELIST.LIST>
        </STOCKITEM>
      </TALLYMESSAGE>
    </DATA>
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
   <IMPORTRESULT>
    <CREATED>0</CREATED>
    <ALTERED>1</ALTERED>
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
    <LEDGER>198</LEDGER>
    <COSTCATEGORY>15</COSTCATEGORY>
    <COSTCENTRE>15</COSTCENTRE>
    <GODOWN>32</GODOWN>
    <STOCKGROUP>10</STOCKGROUP>
    <STOCKCATEGORY>2</STOCKCATEGORY>
    <STOCKITEM>51</STOCKITEM>
    <VOUCHERTYPE>6</VOUCHERTYPE>
    <CURRENCY>52</CURRENCY>
    <UNIT>16</UNIT>
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
    <TAXUNIT>97</TAXUNIT>
    <RETURNMASTER>0</RETURNMASTER>
    <GSTCLASSIFICATION>0</GSTCLASSIFICATION>
    <VOUCHERNUMBERSERIES>98</VOUCHERNUMBERSERIES>
    <VOUCHER>85</VOUCHER>
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

## 9. Part VII: Best Practices & Error Handling

1. **Master Creation Order / Dependencies**:
   When seeding new companies, create inventory masters in the following strict order to avoid reference lookup failures:
   `Units of Measure` -> `Godowns` -> `Stock Categories` -> `Stock Groups` -> `Stock Items` -> `Price Lists`

2. **Negative Stock Valuation Sign Rule**:
   In Tally XML, Opening Values of Asset items carry a **negative sign** (e.g. `<OPENINGVALUE>-25000.00</OPENINGVALUE>`) because Debit balances in Tally's internal ledger math are represented as negative values.

3. **Incremental Sync with `ALTERID`**:
   To sync changes incrementally without downloading the entire catalog:
   ```xml
   <COLLECTION NAME="IncrementalItems">
     <TYPE>StockItem</TYPE>
     <FILTER>AlterIdFilter</FILTER>
   </COLLECTION>
   <SYSTEM TYPE="Formulae" NAME="AlterIdFilter">$AlterID > 10540</SYSTEM>
   ```

---

## 10. Part VIII: Common Tally XML Exceptions, Root Causes & Fixes

This troubleshooting matrix documents all real-world Tally XML exceptions encountered during integration, their technical root causes in Tally's engine, and the exact fixes applied to resolve them:

| Exception / Line Error | Technical Root Cause in Tally | Exact Resolution / Fix Applied |
| :--- | :--- | :--- |
| **`<LINEERROR>Stock Group 'xyz' does not exist!</LINEERROR>`**<br>`<EXCEPTIONS>1</EXCEPTIONS>` | The Stock Item's `<PARENT>` tag references a Stock Group that has not yet been created in the active company. Tally strictly validates foreign master keys on import. | **1.** Follow strict master dependency ordering: Create **Units** $\to$ **Godowns** $\to$ **Stock Categories** $\to$ **Stock Groups** $\to$ **Stock Items**.<br>**2.** Ensure the parent group is committed in Tally before pushing items. |
| **`<LINEERROR>Stock Group 'Primary' does not exist!</LINEERROR>`**<br>or `<LINEERROR>Godown 'Primary' does not exist!</LINEERROR>` | Passing plain `<PARENT>Primary</PARENT>` for top-level Stock Groups or Godowns. In Tally's internal engine, the root keyword `Primary` requires the internal ASCII 0x04 control prefix (`&#4; Primary`). | Use **`<PARENT>&#4; Primary</PARENT>`** for all top-level Stock Groups and Godowns that belong directly to the root. |
| **`<LINEERROR>BAD ORIGINAL NAME</LINEERROR>`**<br>`<EXCEPTIONS>1</EXCEPTIONS>` | Attempting to mutate the `<ORIGINALNAME>` (Formal Name) of an existing Unit during an `Alter` operation. Tally's unit dictionary table prohibits re-mapping original unit descriptors after initial creation. | For Unit alterations, omit the `<ORIGINALNAME>` tag and alter only mutable properties like `<DECIMALPLACES>` and `<UQCDETAILS.LIST>`. |
| **`<LINEERROR>Cannot delete unnamed object: VOUCHER!</LINEERROR>`** | When sending `<VOUCHER ACTION="Delete">`, passing only the child `<GUID>` tag without the `<VOUCHER REMOTEID="...">` attribute on the root tag. | Always specify the `REMOTEID` attribute on the element: `<VOUCHER REMOTEID="{guid}" ACTION="Delete"><GUID>{guid}</GUID></VOUCHER>`. |
| **`<LINEERROR>Godown 'xyz' does not exist!</LINEERROR>`** | An item's opening balance `<BATCHALLOCATIONS.LIST>` or voucher inventory line references a Godown name that is missing or misspelled. | Verify the Godown exists via `<COLLECTION NAME="List of Godowns">` or default to `<GODOWNNAME>Main Location</GODOWNNAME>`. |
| **`<LINEERROR>Cannot Decrease Number of Decimals for 'Unit'!</LINEERROR>`** | In Tally, decimal places on an existing Unit of Measure can be increased (e.g. 0 to 2), but cannot be decreased to prevent precision loss on existing vouchers. | Only update decimal places by incrementing, or create a distinct unit if a lower decimal precision is needed. |
| **`<LINEERROR>Cannot be deleted!</LINEERROR>` on Unit** | The Unit is referenced as a `<BASEUNITS>` / `<ADDITIONALUNITS>` in a Compound Unit, or is assigned to an existing Stock Item. | Delete the parent Compound Unit and remove stock item associations before attempting to delete the base Unit. |
| **Inverted Stock Valuation in Balance Sheet** | Passing a positive number in `<OPENINGVALUE>25000.00</OPENINGVALUE>`. In Tally's double-entry math, Assets (Debit balances) are represented internally as negative values. | Always supply a negative sign for asset opening values: **`<OPENINGVALUE>-25000.00</OPENINGVALUE>`**. |


