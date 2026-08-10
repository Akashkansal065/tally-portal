# TallyPrime API — Full JSON Reference (54 Operations)

TallyPrime's native JSON interface mirrors its XML object model 1:1. Every request is a `POST` to your TallyPrime instance's configured port (default `9000`) with `Content-Type: application/json`. This doc gives every operation from the API Explorer's nav as a working `curl` command with the native JSON envelope.

> **Provenance note:** These payloads are built from TallyPrime's documented native-JSON object schema (ENVELOPE → HEADER/BODY → TALLYMESSAGE → object), not scraped from the Explorer page itself (that page renders samples client-side via JS, which my fetch tool can't execute). Field names and structure match Tally's published schema, but verify against your TallyPrime release before production use — object/field sets shift slightly across versions (e.g. GST fields).

**Base envelope shape (all requests):**
```json
{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "...", "TYPE": "...", "ID": "..." },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ { } ] } }
  }
}
```
Replace `localhost:9000` with your TallyPrime host/port.

---

## A. Accounting Masters

### Ledger

**1. Create a Ledger**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "LEDGER": {
        "@NAME": "ABC Traders",
        "@ACTION": "Create",
        "PARENT": "Sundry Debtors",
        "ISBILLWISEON": "Yes",
        "OPENINGBALANCE": "0",
        "GSTREGISTRATIONTYPE": "Regular",
        "PARTYGSTIN": "27ABCDE1234F1Z5",
        "LEDGERMOBILE": "9876543210",
        "EMAIL": "abc@traders.com"
      }
    } ] } }
  }
}'
```
Response: `<RESPONSE>` block with `CREATED`, `ALTERED`, `LASTVOUCHERID` counts (returned as JSON when native JSON is used).

**2. Alter a Ledger**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "LEDGER": {
        "@NAME": "ABC Traders",
        "@ACTION": "Alter",
        "LEDGERMOBILE": "9998887776",
        "EMAIL": "newcontact@abctraders.com"
      }
    } ] } }
  }
}'
```

**3. Delete a Ledger**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "LEDGER": { "@NAME": "ABC Traders", "@ACTION": "Delete" }
    } ] } }
  }
}'
```

**4. Pull a Ledger**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Object", "ID": "Ledger" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "FETCHLIST": { "FETCH": ["*"] }
    }, "DATA": {} }
  }
}'
```
Response shape:
```json
{ "ENVELOPE": { "LEDGER": { "NAME": "ABC Traders", "PARENT": "Sundry Debtors", "OPENINGBALANCE": "0", "CLOSINGBALANCE": "15400" } } }
```

**5. Pull All Ledgers**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "List of Ledgers" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "List of Ledgers", "@ISMODIFY": "No",
        "TYPE": "Ledger",
        "FETCH": ["NAME", "PARENT", "OPENINGBALANCE", "CLOSINGBALANCE"]
      } } }
    }, "DATA": {} }
  }
}'
```

**6. Pull Ledgers of Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Ledgers Of Group" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Ledgers Of Group", "@ISMODIFY": "No",
        "TYPE": "Ledger",
        "CHILDOF": "Sundry Debtors",
        "FETCH": ["NAME", "PARENT", "CLOSINGBALANCE"]
      } } }
    }, "DATA": {} }
  }
}'
```

### Group

**7. Create a Group**
(Using the `jsonex` payload format via HTTP Headers)
```bash
curl -X POST http://localhost:9000 \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: Import" \
  -H "type: Data" \
  -H "id: All Masters" \
  -d '{
    "static_variables": [
        { "name": "svMstImportFormat", "value": "jsonex" },
        { "name": "svCurrentCompany", "value": "Your Company Name" }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Group", 
                "action": "create",
                "name": "South Bank Accounts" 
            }, 
            "name": "South Bank Accounts",
            "parent": "Bank Accounts",
            "issubledger": "yes"
        }
    ]
}'
```

**8. Alter a Group**
(Using the `jsonex` payload format)
```bash
curl -X POST http://localhost:9000 \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: Import" \
  -H "type: Data" \
  -H "id: All Masters" \
  -d '{
    "static_variables": [
        { "name": "svMstImportFormat", "value": "jsonex" },
        { "name": "svCurrentCompany", "value": "Your Company Name" }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Group",
                "action": "Alter",
                "name": "South Bank Accounts"
            },
            "name": "South Bank Accounts",
            "IsSubLedger": "yes"
        }
    ]
}'
```

**9. Delete a Group**
(Using the `jsonex` payload format)
```bash
curl -X POST http://localhost:9000 \
  -H "content-type: application/json" \
  -H "version: 1" \
  -H "tallyrequest: Import" \
  -H "type: Data" \
  -H "id: All Masters" \
  -d '{
    "static_variables": [
        { "name": "svMstImportFormat", "value": "jsonex" },
        { "name": "svCurrentCompany", "value": "Your Company Name" }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Group",
                "action": "Delete",
                "name": "South Bank Accounts"
            }
        }
    ]
}'
```

**10. Pull a Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Object", "ID": "Group" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "FETCHLIST": { "FETCH": ["*"] }
    }, "DATA": {} }
  }
}'
```

**11. Pull All Groups**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "List of Groups" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "List of Groups", "@ISMODIFY": "No",
        "TYPE": "Group",
        "FETCH": ["NAME", "PARENT"]
      } } }
    }, "DATA": {} }
  }
}'
```

**12. Pull Groups of Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Groups Of Group" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Groups Of Group", "@ISMODIFY": "No",
        "TYPE": "Group",
        "CHILDOF": "Sundry Debtors",
        "FETCH": ["NAME", "PARENT"]
      } } }
    }, "DATA": {} }
  }
}'
```

---

## B. Inventory Masters

### Stock Item

**13. Create a Stock Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKITEM": {
        "@NAME": "Ballpoint Pen - Blue",
        "@ACTION": "Create",
        "PARENT": "Stationery",
        "BASEUNITS": "Nos",
        "GSTAPPLICABLE": "Applicable",
        "HSNCODE": "9608",
        "GSTTYPEOFSUPPLY": "Goods",
        "OPENINGBALANCE": "0",
        "OPENINGRATE": "0",
        "OPENINGVALUE": "0"
      }
    } ] } }
  }
}'
```

**14. Alter a Stock Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKITEM": { "@NAME": "Ballpoint Pen - Blue", "@ACTION": "Alter", "HSNCODE": "9608.10" }
    } ] } }
  }
}'
```

**15. Delete a Stock Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKITEM": { "@NAME": "Ballpoint Pen - Blue", "@ACTION": "Delete" }
    } ] } }
  }
}'
```

**16. Pull a Stock Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Object", "ID": "StockItem" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "FETCHLIST": { "FETCH": ["*"] }
    }, "DATA": {} }
  }
}'
```

**17. Pull All Stock Items**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "List of Stock Items" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "List of Stock Items", "@ISMODIFY": "No",
        "TYPE": "StockItem",
        "FETCH": ["NAME", "PARENT", "BASEUNITS", "CLOSINGBALANCE", "CLOSINGVALUE"]
      } } }
    }, "DATA": {} }
  }
}'
```

**18. Pull Stock Items of Stock Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Stock Items Of Group" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Stock Items Of Group", "@ISMODIFY": "No",
        "TYPE": "StockItem",
        "CHILDOF": "Stationery",
        "FETCH": ["NAME", "CLOSINGBALANCE"]
      } } }
    }, "DATA": {} }
  }
}'
```

### Stock Group

**19. Create a Stock Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKGROUP": { "@NAME": "Stationery", "@ACTION": "Create", "PARENT": "Primary", "ISADDABLE": "Yes" }
    } ] } }
  }
}'
```

**20. Alter a Stock Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKGROUP": { "@NAME": "Stationery", "@ACTION": "Alter", "PARENT": "Primary" }
    } ] } }
  }
}'
```

**21. Delete a Stock Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "STOCKGROUP": { "@NAME": "Stationery", "@ACTION": "Delete" }
    } ] } }
  }
}'
```

**22. Pull a Stock Group**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Object", "ID": "StockGroup" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "FETCHLIST": { "FETCH": ["*"] }
    }, "DATA": {} }
  }
}'
```

**23. Pull All Stock Groups**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "List of Stock Groups" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "List of Stock Groups", "@ISMODIFY": "No",
        "TYPE": "StockGroup",
        "FETCH": ["NAME", "PARENT"]
      } } }
    }, "DATA": {} }
  }
}'
```

**24. Pull Stock Group With Zero Balance**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Zero Balance Stock Groups" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Zero Balance Stock Groups", "@ISMODIFY": "No",
        "TYPE": "StockGroup",
        "FETCH": ["NAME", "CLOSINGBALANCE"],
        "FILTER": ["ZeroBalFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "ZeroBalFilter", "TEXT": "$ClosingBalance = 0" } } }
    }, "DATA": {} }
  }
}'
```

### Units

**25. Create a Simple Unit**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "UNIT": { "@NAME": "Nos", "@ACTION": "Create", "ISSIMPLEUNIT": "Yes", "DECIMALPLACES": "0" }
    } ] } }
  }
}'
```

**26. Create a Compound Unit**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "UNIT": {
        "@NAME": "Box of 10 Nos",
        "@ACTION": "Create",
        "ISSIMPLEUNIT": "No",
        "BASEUNITS": "Nos",
        "ADDITIONALUNITS": "Box",
        "CONVERSION": "10"
      }
    } ] } }
  }
}'
```

**27. Alter a Unit**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "UNIT": { "@NAME": "Nos", "@ACTION": "Alter", "DECIMALPLACES": "2" }
    } ] } }
  }
}'
```

**28. Delete a Unit**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "UNIT": { "@NAME": "Nos", "@ACTION": "Delete" }
    } ] } }
  }
}'
```

**29. Pull a Unit**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Object", "ID": "Unit" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "FETCHLIST": { "FETCH": ["*"] }
    }, "DATA": {} }
  }
}'
```

**30. Pull All Units**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "List of Units" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "List of Units", "@ISMODIFY": "No",
        "TYPE": "Unit",
        "FETCH": ["NAME", "ISSIMPLEUNIT", "BASEUNITS", "CONVERSION"]
      } } }
    }, "DATA": {} }
  }
}'
```

---

## C. Transactions — Accounting Vouchers

### Payment

**31. Create a Payment with Banking Details**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Payment",
        "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Payment",
        "NARRATION": "Payment to ABC Traders via bank transfer",
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "ABC Traders", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-10000",
            "BANKALLOCATIONS.LIST": { "TRANSACTIONTYPE": "Others", "INSTRUMENTDATE": "20260729", "TRANSACTIONID": "TXN00123" } },
          { "LEDGERNAME": "HDFC Bank", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "10000" }
        ]
      }
    } ] } }
  }
}'
```

**32. Create a Payment with Cash**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Payment",
        "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Payment",
        "NARRATION": "Cash payment for office supplies",
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "Office Supplies", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-1500" },
          { "LEDGERNAME": "Cash", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "1500" }
        ]
      }
    } ] } }
  }
}'
```

**33. Alter a Payment**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Payment", "@ACTION": "Alter",
        "@REMOTEID": "guid-of-existing-voucher",
        "VOUCHERNUMBER": "12",
        "NARRATION": "Corrected narration"
      }
    } ] } }
  }
}'
```

**34. Delete a Payment**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": { "@VCHTYPE": "Payment", "@ACTION": "Delete", "VOUCHERNUMBER": "12", "DATE": "20260729" }
    } ] } }
  }
}'
```

**35. Pull all Payment vouchers**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Payment Vouchers" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Payment Vouchers", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["PaymentFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "PaymentFilter", "TEXT": "$VoucherTypeName = \"Payment\"" } } }
    }, "DATA": {} }
  }
}'
```

**36. Pull all Payment vouchers for a period**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Payment Vouchers Period" },
    "BODY": { "DESC": {
      "STATICVARIABLES": {
        "SVCURRENTCOMPANY": "Your Company Name",
        "SVFROMDATE": "20260401",
        "SVTODATE": "20260729"
      },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Payment Vouchers Period", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["PaymentFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "PaymentFilter", "TEXT": "$VoucherTypeName = \"Payment\"" } } }
    }, "DATA": {} }
  }
}'
```

### Receipt

**37. Create a Receipt with Banking Details**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Receipt", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Receipt",
        "NARRATION": "Receipt from XYZ Corp via NEFT",
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "HDFC Bank", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-25000",
            "BANKALLOCATIONS.LIST": { "TRANSACTIONTYPE": "Others", "INSTRUMENTDATE": "20260729", "TRANSACTIONID": "NEFT0099" } },
          { "LEDGERNAME": "XYZ Corp", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "25000" }
        ]
      }
    } ] } }
  }
}'
```

**38. Create a Receipt with Cash Details**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Receipt", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Receipt",
        "NARRATION": "Cash receipt from walk-in customer",
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "Cash", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-500" },
          { "LEDGERNAME": "Walk-in Sales", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "500" }
        ]
      }
    } ] } }
  }
}'
```

**39. Alter a Receipt**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Receipt", "@ACTION": "Alter",
        "VOUCHERNUMBER": "8", "DATE": "20260729",
        "NARRATION": "Corrected receipt narration"
      }
    } ] } }
  }
}'
```

**40. Delete a Receipt**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": { "@VCHTYPE": "Receipt", "@ACTION": "Delete", "VOUCHERNUMBER": "8", "DATE": "20260729" }
    } ] } }
  }
}'
```

**41. Pull all Receipt vouchers**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Receipt Vouchers" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Receipt Vouchers", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["ReceiptFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "ReceiptFilter", "TEXT": "$VoucherTypeName = \"Receipt\"" } } }
    }, "DATA": {} }
  }
}'
```

**42. Pull all Receipt vouchers for a period**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Receipt Vouchers Period" },
    "BODY": { "DESC": {
      "STATICVARIABLES": {
        "SVCURRENTCOMPANY": "Your Company Name",
        "SVFROMDATE": "20260401",
        "SVTODATE": "20260729"
      },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Receipt Vouchers Period", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["ReceiptFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "ReceiptFilter", "TEXT": "$VoucherTypeName = \"Receipt\"" } } }
    }, "DATA": {} }
  }
}'
```

### Sales

**43. Create Sales with Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Sales", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Sales",
        "PARTYLEDGERNAME": "ABC Traders",
        "ALLINVENTORYENTRIES.LIST": [ {
          "STOCKITEMNAME": "Ballpoint Pen - Blue",
          "RATE": "10/Nos",
          "AMOUNT": "1000",
          "ACTUALQTY": "100 Nos",
          "BILLEDQTY": "100 Nos"
        } ],
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "ABC Traders", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-1000" },
          { "LEDGERNAME": "Sales Account", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "1000" }
        ]
      }
    } ] } }
  }
}'
```

**44. Create Sales with GST**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Sales", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Sales",
        "PARTYLEDGERNAME": "ABC Traders",
        "PLACEOFSUPPLY": "Maharashtra",
        "ALLINVENTORYENTRIES.LIST": [ {
          "STOCKITEMNAME": "Ballpoint Pen - Blue",
          "RATE": "10/Nos",
          "AMOUNT": "1000",
          "ACTUALQTY": "100 Nos",
          "BILLEDQTY": "100 Nos",
          "GSTRATE": "18",
          "GSTHSNNAME": "9608"
        } ],
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "ABC Traders", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-1180" },
          { "LEDGERNAME": "Sales Account", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "1000" },
          { "LEDGERNAME": "Output CGST", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "90" },
          { "LEDGERNAME": "Output SGST", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "90" }
        ]
      }
    } ] } }
  }
}'
```

**45. Alter a Sales**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Sales", "@ACTION": "Alter",
        "VOUCHERNUMBER": "45", "DATE": "20260729",
        "NARRATION": "Corrected invoice narration"
      }
    } ] } }
  }
}'
```

**46. Delete a Sales**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": { "@VCHTYPE": "Sales", "@ACTION": "Delete", "VOUCHERNUMBER": "45", "DATE": "20260729" }
    } ] } }
  }
}'
```

**47. Pull all Sales vouchers**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Sales Vouchers" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Sales Vouchers", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["SalesFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "SalesFilter", "TEXT": "$VoucherTypeName = \"Sales\"" } } }
    }, "DATA": {} }
  }
}'
```

**48. Pull all Sales vouchers for a period**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Sales Vouchers Period" },
    "BODY": { "DESC": {
      "STATICVARIABLES": {
        "SVCURRENTCOMPANY": "Your Company Name",
        "SVFROMDATE": "20260401",
        "SVTODATE": "20260729"
      },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Sales Vouchers Period", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["SalesFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "SalesFilter", "TEXT": "$VoucherTypeName = \"Sales\"" } } }
    }, "DATA": {} }
  }
}'
```

### Purchase

**49. Create Purchase with Item**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Purchase", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Purchase",
        "PARTYLEDGERNAME": "Paper Suppliers Ltd",
        "ALLINVENTORYENTRIES.LIST": [ {
          "STOCKITEMNAME": "Ballpoint Pen - Blue",
          "RATE": "6/Nos",
          "AMOUNT": "600",
          "ACTUALQTY": "100 Nos",
          "BILLEDQTY": "100 Nos"
        } ],
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "Purchase Account", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-600" },
          { "LEDGERNAME": "Paper Suppliers Ltd", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "600" }
        ]
      }
    } ] } }
  }
}'
```

**50. Create Purchase with GST**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Purchase", "@ACTION": "Create",
        "DATE": "20260729",
        "VOUCHERTYPENAME": "Purchase",
        "PARTYLEDGERNAME": "Paper Suppliers Ltd",
        "PLACEOFSUPPLY": "Maharashtra",
        "ALLINVENTORYENTRIES.LIST": [ {
          "STOCKITEMNAME": "Ballpoint Pen - Blue",
          "RATE": "6/Nos",
          "AMOUNT": "600",
          "ACTUALQTY": "100 Nos",
          "BILLEDQTY": "100 Nos",
          "GSTRATE": "18",
          "GSTHSNNAME": "9608"
        } ],
        "ALLLEDGERENTRIES.LIST": [
          { "LEDGERNAME": "Purchase Account", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-708" },
          { "LEDGERNAME": "Input CGST", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-54" },
          { "LEDGERNAME": "Input SGST", "ISDEEMEDPOSITIVE": "Yes", "AMOUNT": "-54" },
          { "LEDGERNAME": "Paper Suppliers Ltd", "ISDEEMEDPOSITIVE": "No", "AMOUNT": "708" }
        ]
      }
    } ] } }
  }
}'
```

**51. Alter a Purchase**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": {
        "@VCHTYPE": "Purchase", "@ACTION": "Alter",
        "VOUCHERNUMBER": "22", "DATE": "20260729",
        "NARRATION": "Corrected purchase entry"
      }
    } ] } }
  }
}'
```

**52. Delete a Purchase**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Import Data", "TYPE": "Data", "ID": "" },
    "BODY": { "DESC": {}, "DATA": { "TALLYMESSAGE": [ {
      "VOUCHER": { "@VCHTYPE": "Purchase", "@ACTION": "Delete", "VOUCHERNUMBER": "22", "DATE": "20260729" }
    } ] } }
  }
}'
```

**53. Pull all Purchase vouchers**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Purchase Vouchers" },
    "BODY": { "DESC": {
      "STATICVARIABLES": { "SVCURRENTCOMPANY": "Your Company Name" },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Purchase Vouchers", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["PurchaseFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "PurchaseFilter", "TEXT": "$VoucherTypeName = \"Purchase\"" } } }
    }, "DATA": {} }
  }
}'
```

**54. Pull all Purchase vouchers for a period**
```bash
curl -X POST http://localhost:9000 -H "Content-Type: application/json" -d '{
  "ENVELOPE": {
    "HEADER": { "VERSION": "1", "TALLYREQUEST": "Export Data", "TYPE": "Collection", "ID": "Purchase Vouchers Period" },
    "BODY": { "DESC": {
      "STATICVARIABLES": {
        "SVCURRENTCOMPANY": "Your Company Name",
        "SVFROMDATE": "20260401",
        "SVTODATE": "20260729"
      },
      "TDL": { "TDLMESSAGE": { "COLLECTION": {
        "@NAME": "Purchase Vouchers Period", "@ISMODIFY": "No",
        "TYPE": "Voucher",
        "FILTER": ["PurchaseFilter"]
      }, "SYSTEM": { "@TYPE": "Formulae", "@NAME": "PurchaseFilter", "TEXT": "$VoucherTypeName = \"Purchase\"" } } }
    }, "DATA": {} }
  }
}'
```

---

## Notes for integration into your FastAPI app

- **Create/Alter/Delete** all use `TALLYREQUEST: "Import Data"` — the only difference is the `@ACTION` attribute and which fields are populated.
- **Pull single object** uses `TYPE: "Object"` with `ID` = object class name (`Ledger`, `Group`, `StockItem`, etc.) and needs the object's name passed via context (Tally resolves the "current" object from a preceding `SET` or a `NAME` static variable depending on release — check your version's exact single-object pull syntax, this varies more than collection pulls across releases).
- **Pull all / filtered** uses `TYPE: "Collection"` with a custom `COLLECTION` definition under `TDL.TDLMESSAGE` — this is the most reliable and portable way to pull data and is what production integrations typically use.
- Dates are always `YYYYMMDD` with no separators.
- Amounts: debit/credit sign convention is `ISDEEMEDPOSITIVE: "Yes"` + negative `AMOUNT` for the debit side of a ledger entry in some voucher types — verify sign convention against your TallyPrime release since it differs slightly between Payment/Receipt vs Sales/Purchase.
