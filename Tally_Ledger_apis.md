# TallyPrime API — Complete Ledger Operations & Curl Reference

This reference documents the exact HTTP headers, JSON (`jsonex`), and XML payloads for all **Ledger Master** operations in TallyPrime, matching official Tally schema requirements and verified native keys.

- **1. Create a Ledger (Verified Tested JSON Payload)**
- **2. Alter a Ledger (Verified Tested JSON Payload)**
- **3. Delete a Ledger (Verified Tested JSON Payload & Response)**
- **4. Pull a Specific Ledger (Single Object Export with Custom TDL Aadhaar Field)**
- **5. Pull All Ledgers Collection (`jsonex` Export)**
- **6. Pull Ledgers of Group (`jsonex` TDL Collection Export)**
- **7. How to Identify Groups & Hierarchy of a Ledger**

---

### 📌 Verified Native & TDL UDF Field Mappings

These are the exact native field keys and TDL UDF storage keys in TallyPrime:

| Field Category | Exact Tally Field Key | Data Type | Storage Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Aadhaar Number** | **`LWLedAdharNoStore`** | String | 🎯 **Custom TDL UDF** | **Exact storage key for Aadhaar Number defined in `[System:udf]`** |
| **Parent Group** | `parent` | String | Native | Direct Account Group under which ledger is created |
| **Group Debit Parent** | `grpdebitparent` | String | Native | System Debit Group Hierarchy |
| **Group Credit Parent**| `grpcreditparent` | String | Native | System Credit Group Hierarchy |
| **Country of Residence**| `countryofresidence` | String | 🚨 **CRITICAL** (`"India"`) | **Must be provided for `priorstatename` & `pincode` to be saved** |
| **ISD Country Code** | `ledgercountryisdcode` | String | Native | International Phone ISD Country Code |
| **Currency Name** | `currencyname` | String | Native | Ledger Currency Symbol / Code |
| **State Name** | `priorstatename` | String | Native | State Name (Requires `countryofresidence`) |
| **Pincode** | `pincode` | String | Native | 6-Digit ZIP / Postal Code (Requires `countryofresidence`) |
| **Ledger Name & Alias**| `languagename` | Array of Objects | Native | Primary name (1st string) + Aliases (2nd+ strings) |
| **GSTIN Number** | `partygstin` | String | Native | 15-Digit GSTIN Number |
| **PAN Number** | `incometaxnumber` | String | Native | 10-Digit PAN Number |
| **Contact Person** | `ledgercontact` | String | Native | Primary Contact Person Name |
| **Mobile Number** | `ledgermobile` | String | Native | Mobile Phone Number |
| **Phone Number** | `ledgerphone` | String | Native | Landline Phone Number |
| **Email** | `email` | String | Native | Primary Contact Email |
| **GST Registration** | `gstregistrationtype` / `vatdealertype` | String | Native | GST Registration Category |
| **GST Reg Details** | `ledgstregdetails` | Array of Objects | Native | GST details array with `transporterid`, `placeofsupply`, `applicablefrom` |
| **Transporter ID** | `transporterid` | String | Native | Transporter E-way Bill ID inside `ledgstregdetails` |
| **Is Transporter** | `istransporter` | Logical (Boolean) | Native | Flag indicating if ledger is a goods transporter |
| **Place of Supply** | `placeofsupply` | String | Native | State for GST place of supply inside `ledgstregdetails` |
| **Other Territory** | `isothterritoryassessee` | Logical (Boolean) | Native | Flag for Other Territory / Special UT assessee |
| **Common Party** | `iscommonparty` | Logical (Boolean) | Native | Flag indicating if party is both debtor and creditor |
| **Inventory Affected** | `isaffectstock` | Logical (Boolean) | Native | Flag indicating if ledger transactions affect inventory stock |
| **Cost Centres On** | `iscostcentreson` | Logical (Boolean) | Native | Flag for Cost Centre allocation |
| **Notes / Remarks** | `notes` | String | Native | Internal ledger remarks and instructions |
| **Opening Balance** | `openingbalance` | Amount String | Native | Opening balance (`-ve` for Debit Dr, `+ve` for Credit Cr) |
| **Bill Allocations** | `billallocations` | Array of Objects | Native | Bill-by-bill breakdown array for Opening Balance |
| **Credit Limit** | `creditlimit` | Amount String | Native | Credit Limit |
| **Credit Days** | `creditdays` | String | Native | Payment terms |
| **Address & Mailing** | `ledmailingdetails` | Array of Objects | Native | Address array, state, country inside `ledmailingdetails` |

> ⚠️ **Important Dependency**: Tally Prime will **ignore** `priorstatename` (State) and `pincode` (ZIP Code) unless **`countryofresidence`: "India"** is explicitly included in the request body.

---

## 1. Create a Ledger (With Full Mailing & GST Details & Custom TDL Aadhaar UDF)

```bash
curl --location 'http://192.168.71.129:9000/' \
  --header 'content-type: application/json' \
  --header 'version: 1' \
  --header 'tallyrequest: Import' \
  --header 'type: Data' \
  --header 'id: All Masters' \
  --data '{
    "static_variables": [
        {
            "name": "svMstImportFormat",
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
                "type": "Ledger",
                "action": "create",
                "name": "AAA Testing s Solutions Pvt Ltd"
            },
            "name": "AAA Testing s Solutions Pvt Ltd",
            "parent": "Sundry Debtors",
            "currencyname": "INR",
            "ledgercountryisdcode": "+91",
            "mailingname": "AAA Testing s Solutions Private Limited",
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "AAA Testing s Solutions Pvt Ltd",
                        "Aaaaaaa"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": "1033"
                    }
                }
            ],
            "countryofresidence": "India",
            "priorstatename": "Haryana",
            "pincode": "122002",
            "countryname": "India",
            "ledmailingdetails": [
                {
                    "address": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Plot No 78, Cyber City",
                        "Phase 2, Sector 18",
                        "Udyog Vihar",
                        "Gurugram"
                    ],
                    "mailingname": "AAA Testing s Solutions Private Limited",
                    "applicablefrom": "20250401",
                    "country": "India",
                    "state": "Haryana",
                    "pincode": "122002"
                }
            ],
            "ledgercontact": "Mr. Vikram Malhotra",
            "ledgermobile": "9810012345",
            "ledgerphone": "0124-4567890",
            "email": "accounts@apextechsolutions.com",
            "incometaxnumber": "AAACA1234A",
            "partygstin": "07AAACA1234A1Z5",
            "gstregistrationtype": "Regular",
            "vatdealertype": "Regular",
            "ledgstregdetails": [
                {
                    "applicablefrom": "20250401",
                    "gstregistrationtype": "Regular",
                    "transporterid": "1234561",
                    "state": "Haryana",
                    "placeofsupply": "Haryana",
                    "gstin": "07AAACA1234A1Z5",
                    "isothterritoryassessee": false,
                    "considerpurchaseforexport": false,
                    "istransporter": true,
                    "iscommonparty": false
                }
            ],
            "lwledadlharnosstore": "123456789012",
            "isbillwiseon": true,
            "isaffectstock": false,
            "iscostcentreson": false,
            "ischequeprintingenabled": true,
            "isdeemedpositive": true,
            "creditlimit": "500000.00",
            "creditdays": "45 Days",
            "openingbalance": "-150000.00",
            "paymentdetails": [
                {
                    "transactiontype": "UPI",
                    "transacttype": "UPI",
                    "accountnumber": "1232121211",
                    "ifsccode": "PUNB0400700",
                    "bankname": "Punjab National Bank",
                    "emailid": "8979921514@upi",
                    "payeeupiid": "8979921514@upi"
                }
            ],
            "billallocations": [
                {
                    "billdate": "20250331",
                    "name": "OP1",
                    "openingbalance": "-100000.00"
                },
                {
                    "billdate": "20250331",
                    "name": "OP2",
                    "openingbalance": "-50000.00"
                }
            ]
        }
    ]
}'
```

---

## 2. Alter a Ledger (Update Address, GST Registration & Contact)

```bash
curl --location 'http://192.168.71.129:9000/' \
  --header 'content-type: application/json' \
  --header 'version: 1' \
  --header 'tallyrequest: Import' \
  --header 'type: Data' \
  --header 'id: All Masters' \
  --data '{
    "static_variables": [
        {
            "name": "svMstImportFormat",
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
                "type": "Ledger",
                "action": "alter",
                "name": "AAA Testing s Solutions Pvt Ltd"
            },
            "name": "AAA Testing s Solutions Pvt Ltd",
            "parent": "Sundry Debtors",
            "currencyname": "INR",
            "ledgercountryisdcode": "+91",
            "mailingname": "AAA Testing s Solutions Private Limited",
            "countryofresidence": "India",
            "priorstatename": "Uttar Pradesh",
            "pincode": "250004",
            "countryname": "India",
            "ledmailingdetails": [
                {
                    "address": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "#89 Raj Arcade",
                        "S.V.Road",
                        "VileParle (West)"
                    ],
                    "mailingname": "AAA Testing s Solutions Private Limited",
                    "applicablefrom": "20250401",
                    "country": "India",
                    "state": "Uttar Pradesh",
                    "pincode": "250004"
                }
            ],
            "ledgercontact": "Mr. Vikram Malhotra",
            "ledgermobile": "9810099999",
            "ledgerphone": "0124-4567890",
            "email": "finance@apextechsolutions.com",
            "incometaxnumber": "AAACA1234A",
            "partygstin": "07AAACA1234A1Z5",
            "gstregistrationtype": "Regular",
            "vatdealertype": "Regular",
            "ledgstregdetails": [
                {
                    "applicablefrom": "20250401",
                    "gstregistrationtype": "Regular",
                    "gstin": "07AAACA1234A1Z5"
                }
            ],
            "lwledadlharnosstore": "987654321098",
            "isbillwiseon": true,
            "ischequeprintingenabled": true,
            "isdeemedpositive": true,
            "creditlimit": "750000.00",
            "creditdays": "30 Days",
            "openingbalance": "-150000.00"
        }
    ]
}'
```
```

---

## 3. Delete a Ledger (Verified Minimal Delete Payload & Response)

### Request Payload:
```bash
curl --location 'https://sneh-distributors.hostlocal.app/' \
  -H 'content-type: application/json' \
  -H 'version: 1' \
  -H 'tallyrequest: Import' \
  -H 'type: Data' \
  -H 'id: All Masters' \
  -d '{
    "static_variables": [
        {
            "name": "svMstImportFormat",
            "value": "jsonex"
        },
        {
            "name": "svCurrentCompany",
            "value": "Sneh Distributors"
        }
    ],
    "tallymessage": [
        {
            "metadata": {
                "type": "Ledger",
                "action": "Delete",
                "name": "Bank Of Baroda"
            }
        }
    ]
}'
```

### Verified Response:
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
            "exceptions": 0
        }
    }
}
```

---

## 4. Pull a Specific Ledger (Single Object Export with TDL Aadhaar UDF)

### Request Payload:
```bash
curl --location 'http://192.168.71.129:9000/' \
  --header 'content-type: application/json' \
  --header 'version: 1' \
  --header 'tallyrequest: export' \
  --header 'type: object' \
  --header 'subtype: Ledger' \
  --header 'id: AAA Testing s Solutions Pvt Ltd' \
  --data '{
    "static_variables": [
        {
            "name": "svExportFormat",
            "value": "jsonEx"
        },
        {
            "name": "svCurrentCompany",
            "value": "Bhrama Enterprises"
        }
    ],
    "fetch_list": [
        "*",
        "guid",
        "masterid",
        "alterid",
        "sortposition",
        "parent",
        "grpdebitparent",
        "grpcreditparent",
        "sysdebitparent",
        "syscreditparent",
        "mailingname",
        "address",
        "ledmailingdetails",
        "ledgstregdetails",
        "languagename",
        "billallocations",
        "statename",
        "priorstatename",
        "pincode",
        "countryname",
        "countryofresidence",
        "ledgercountryisdcode",
        "currencyname",
        "gstregistrationtype",
        "partygstin",
        "gstin",
        "panNumber",
        "incometaxnumber",
        "description",
        "ledgercontact",
        "ledgerphone",
        "ledgermobile",
        "email",
        "emailcc",
        "website",
        "creditlimit",
        "creditdays",
        "isbillwiseon",
        "openingbalance",
        "closingbalance",
        "updateddatetime",
        "objectupdateaction",
        "remotealtguid",
        "lwledadlharnosstore"
    ]
}'
```

### Verified JSON Response Payload:
```json
{
    "status": "1",
    "tallymessage": [
        {
            "metadata": {
                "type": "Ledger",
                "name": "AAA Testing s Solutions Pvt Ltd",
                "reservedname": "",
                "id": "369",
                "reqname": "AAA Testing s Solutions Pvt Ltd"
            },
            "address": [
                {
                    "metadata": true,
                    "type": "String"
                },
                "Plot No 78, Cyber City",
                "Phase 2, Sector 18",
                "Udyog Vihar",
                "Gurugram"
            ],
            "guid": {
                "type": "String",
                "value": "f0347998-2c19-4a5e-a4ed-01f589cb92a5-00000171"
            },
            "currencyname": {
                "type": "String",
                "value": "INR"
            },
            "email": {
                "type": "String",
                "value": "accounts@apextechsolutions.com"
            },
            "priorstatename": {
                "type": "String",
                "value": "Haryana"
            },
            "pincode": {
                "type": "String",
                "value": "122002"
            },
            "incometaxnumber": {
                "type": "String",
                "value": "AAACA1234A"
            },
            "countryname": {
                "type": "String",
                "value": "India"
            },
            "gstregistrationtype": {
                "type": "String",
                "value": "Regular"
            },
            "vatdealertype": {
                "type": "String",
                "value": "Regular"
            },
            "parent": {
                "type": "String",
                "value": "Sundry Debtors"
            },
            "mailingname": {
                "type": "String",
                "value": "AAA Testing s Solutions Private Limited"
            },
            "remotealtguid": {
                "type": "String",
                "value": "f0347998-2c19-4a5e-a4ed-01f589cb92a5"
            },
            "objectupdateaction": {
                "type": "String",
                "value": "Alter"
            },
            "countryofresidence": {
                "type": "String",
                "value": "India"
            },
            "ledgerphone": {
                "type": "String",
                "value": "0124-4567890"
            },
            "ledgercontact": {
                "type": "String",
                "value": "Mr. Vikram Malhotra"
            },
            "ledgermobile": {
                "type": "String",
                "value": "9810012345"
            },
            "ledgercountryisdcode": {
                "type": "String",
                "value": "+91"
            },
            "partygstin": {
                "type": "String",
                "value": "07AAACA1234A1Z5"
            },
            "lwledadlharnosstore": {
                "type": "String",
                "value": "123456789012"
            },
            "isbillwiseon": {
                "type": "Logical",
                "value": true
            },
            "iscostcentreson": {
                "type": "Logical",
                "value": false
            },
            "isdeemedpositive": {
                "type": "Logical",
                "value": true
            },
            "affectsstock": {
                "type": "Logical",
                "value": false
            },
            "ischequeprintingenabled": {
                "type": "Logical",
                "value": true
            },
            "sortposition": {
                "type": "Number",
                "value": " 1000"
            },
            "alterid": {
                "type": "Number",
                "value": " 766"
            },
            "masterid": {
                "type": "Number",
                "value": " 369"
            },
            "closingbalance": {
                "type": "Amount",
                "value": "-150000.00"
            },
            "openingbalance": {
                "type": "Amount",
                "value": "-150000.00"
            },
            "creditlimit": {
                "type": "Amount",
                "value": "500000.00"
            },
            "updateddatetime": {
                "type": "DateTime",
                "value": "20260803212549000"
            },
            "languagename": [
                {
                    "name": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "AAA Testing s Solutions Pvt Ltd",
                        "Aaaaaaa"
                    ],
                    "languageid": {
                        "type": "Number",
                        "value": " 1033"
                    }
                }
            ],
            "billallocations": [
                {
                    "billdate": {
                        "type": "Date",
                        "value": "20250331"
                    },
                    "name": {
                        "type": "String",
                        "value": "OP1"
                    },
                    "billcreditperiod": {
                        "type": "Due Date",
                        "value": "31-Mar-25"
                    },
                    "isadvance": {
                        "type": "Logical",
                        "value": false
                    },
                    "openingbalance": {
                        "type": "Amount",
                        "value": "-100000.00"
                    }
                },
                {
                    "billdate": {
                        "type": "Date",
                        "value": "20250331"
                    },
                    "name": {
                        "type": "String",
                        "value": "OP2"
                    },
                    "billcreditperiod": {
                        "type": "Due Date",
                        "value": "31-Mar-25"
                    },
                    "isadvance": {
                        "type": "Logical",
                        "value": false
                    },
                    "openingbalance": {
                        "type": "Amount",
                        "value": "-50000.00"
                    }
                }
            ],
            "ledgstregdetails": [
                {
                    "applicablefrom": {
                        "type": "Date",
                        "value": "20250401"
                    },
                    "gstregistrationtype": {
                        "type": "String",
                        "value": "Regular"
                    },
                    "gstin": {
                        "type": "String",
                        "value": "09AAACA1234A1Z5"
                    }
                }
            ],
            "ledmailingdetails": [
                {
                    "address": [
                        {
                            "metadata": true,
                            "type": "String"
                        },
                        "Plot No 78, Cyber City",
                        "Phase 2, Sector 18",
                        "Udyog Vihar",
                        "Gurugram"
                    ],
                    "applicablefrom": {
                        "type": "Date",
                        "value": "20250401"
                    },
                    "pincode": {
                        "type": "String",
                        "value": "122002"
                    },
                    "mailingname": {
                        "type": "String",
                        "value": "AAA Testing s Solutions Private Limited"
                    },
                    "state": {
                        "type": "String",
                        "value": "Haryana"
                    },
                    "country": {
                        "type": "String",
                        "value": "India"
                    }
                }
            ]
        }
    ]
}
```

---

## 5. Pull All Ledgers Collection (`jsonex` Export Format)

```bash
curl --location 'https://sneh-distributors.hostlocal.app/' \
  -H 'content-type: application/json' \
  -H 'version: 1' \
  -H 'tallyrequest: export' \
  -H 'type: collection' \
  -H 'id: List of Ledgers' \
  -d '{
    "static_variables": [
      {
        "name": "svExportFormat",
        "value": "jsonex"
      },
      {
        "name": "svCurrentCompany",
        "value": "Sneh Distributors"
      }
    ]
}'
```

---

## 6. Pull Ledgers of Group (TDL Collection Definition Export with Aadhaar UDF)

```bash
curl --location 'https://sneh-distributors.hostlocal.app/' \
  -H 'content-type: application/json' \
  -H 'version: 1' \
  -H 'tallyrequest: export' \
  -H 'type: collection' \
  -H 'id: TSPLBankLedgers' \
  -d '{
  "static_variables": [
    {
      "name": "svExportFormat",
      "value": "jsonex"
    },
    {
      "name": "svCurrentCompany",
      "value": "Sneh Distributors"
    }
  ],
  "tdlmessage": [
    {
      "definitions": [
        {
          "metadata": {
            "name": "TSPLBankLedgers",
            "type": "Collection"
          },
          "attributes": [
            {
              "Type": "Ledger"
            },
            {
              "Child Of": "$$GroupBank"
            },
            {
              "Native Method": "Name, Parent, OpeningBalance, ClosingBalance, LWLedAdharNoStore, Mailing Name, Bank Details"
            }
          ]
        }
      ]
    }
  ]
}'
```

---

## 7. How to Identify Groups & Hierarchy of a Ledger

When you pull a ledger from Tally Prime, the following properties identify its Group and parent hierarchy:

### 📌 1. Direct Parent Group (`parent`)
The **`parent`** key gives the immediate Account Group under which the ledger is created:
```json
"parent": {
    "type": "String",
    "value": "Sundry Debtors"
}
```

### 📌 2. System Group Hierarchy Fields
- **`grpdebitparent`**: Internal debit parent group name.
- **`sysdebitparent`**: Top-level system debit category (e.g. `Primary`, `Current Assets`).
- **`grpcreditparent`**: Internal credit parent group name.
- **`syscreditparent`**: Top-level system credit category.

### 📌 3. How to Fetch All Groups Collection in Tally
To fetch all Account Groups (and their parent group hierarchy) in the company to build a full group tree:

```bash
curl --location 'https://sneh-distributors.hostlocal.app/' \
  -H 'content-type: application/json' \
  -H 'version: 1' \
  -H 'tallyrequest: export' \
  -H 'type: collection' \
  -H 'id: List of Groups' \
  -d '{
    "static_variables": [
      {
        "name": "svExportFormat",
        "value": "jsonex"
      },
      {
        "name": "svCurrentCompany",
        "value": "Sneh Distributors"
      }
    ]
}'
```

The response returns every group with its **`name`** and **`parent`** (e.g. `Sundry Debtors` → `Current Assets` → `Primary`), allowing you to resolve the complete group chain for any ledger!