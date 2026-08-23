import os
import json
import re
import logging
from decimal import Decimal
from datetime import date, datetime
from typing import Dict, Any, Optional, List, Tuple, Union
import xml.etree.ElementTree as ET

logger = logging.getLogger("uvicorn.error")

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "schemas", "tally_definitions")

def _normalize_name(name: str) -> str:
    """Normalize tag or property name: lowercase, strip all spaces, dots, underscores, dashes."""
    return re.sub(r'[\s\._\-]', '', str(name).lower())

class TallySchemaRegistry:
    """
    Registry for official Tally Prime v7.0 JSON Schemas.
    Provides fast lookup of properties, datatypes, and collection metadata.
    """
    _instance: Optional['TallySchemaRegistry'] = None
    _schemas: Dict[str, Dict[str, Any]] = {}
    _normalized_props: Dict[str, Dict[str, Dict[str, Any]]] = {}

    @classmethod
    def get_instance(cls) -> 'TallySchemaRegistry':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, schema_dir: Optional[str] = None):
        self.schema_dir = schema_dir or SCHEMA_DIR
        self._load_all_schemas()

    def _load_all_schemas(self):
        if not os.path.isdir(self.schema_dir):
            logger.warning(f"Tally schema definitions directory not found at {self.schema_dir}")
            return

        for filename in os.listdir(self.schema_dir):
            if filename.endswith(".json") and filename != "index.json":
                object_name = filename[:-5]
                filepath = os.path.join(self.schema_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        data = json.load(f)
                    self._schemas[object_name] = data
                    
                    # Build fast normalized lookup for properties
                    norm_map = {}
                    for prop_name, prop_meta in data.get("Properties", {}).items():
                        norm_key = _normalize_name(prop_name)
                        norm_map[norm_key] = prop_meta
                    self._normalized_props[object_name.lower()] = norm_map
                except Exception as e:
                    logger.error(f"Error loading Tally schema file {filename}: {e}")

        logger.info(f"✅ Loaded {len(self._schemas)} Tally schema definitions from {self.schema_dir}")

    def get_schema(self, object_type: str) -> Optional[Dict[str, Any]]:
        return self._schemas.get(object_type)

    def get_property(self, object_type: str, prop_name: str) -> Optional[Dict[str, Any]]:
        norm_obj = object_type.lower()
        obj_props = self._normalized_props.get(norm_obj)
        if not obj_props:
            return None
        return obj_props.get(_normalize_name(prop_name))

    def get_datatype(self, object_type: str, prop_name: str) -> Optional[str]:
        prop = self.get_property(object_type, prop_name)
        if prop and "Meta" in prop and "Datatype" in prop["Meta"]:
            return prop["Meta"]["Datatype"]
        return None

    def is_complex(self, object_type: str, prop_name: str) -> bool:
        prop = self.get_property(object_type, prop_name)
        return bool(prop and prop.get("IsComplex"))

    def is_repeated(self, object_type: str, prop_name: str) -> bool:
        prop = self.get_property(object_type, prop_name)
        if prop and "Meta" in prop:
            return prop["Meta"].get("Is Repeated", "").strip().lower() == "yes"
        return False


class TallySchemaValidator:
    """
    Validation engine that verifies Tally XML payloads and Python models against
    official Tally Prime v7.0 schema rules to guarantee 100% two-way sync fidelity.
    """
    def __init__(self, registry: Optional[TallySchemaRegistry] = None):
        self.registry = registry or TallySchemaRegistry.get_instance()

    @staticmethod
    def escape_xml(text: Any) -> str:
        """Escape XML special characters according to Tally XML requirements."""
        if text is None:
            return ""
        s = str(text)
        return (
            s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;")
        )

    @staticmethod
    def format_date(d: Union[date, datetime, str, None]) -> str:
        """Format a date or datetime object into Tally standard YYYYMMDD string."""
        if not d:
            return ""
        if isinstance(d, (datetime, date)):
            return d.strftime("%Y%m%d")
        clean = str(d).strip().replace("-", "").replace("/", "")[:8]
        return clean

    @staticmethod
    def format_logical(val: Any) -> str:
        """Format a boolean or truthy value into 'Yes' / 'No' for Tally XML."""
        if isinstance(val, bool):
            return "Yes" if val else "No"
        if isinstance(val, str):
            return "Yes" if val.strip().lower() in ("yes", "true", "1", "t", "y") else "No"
        return "Yes" if bool(val) else "No"

    @staticmethod
    def format_amount(val: Any, decimals: int = 2) -> str:
        """Format an amount value with standard precision."""
        if val is None or val == "":
            return "0.00"
        try:
            d = Decimal(str(val))
            return f"{d:.{decimals}f}"
        except Exception:
            return str(val)

    def validate_field(self, object_type: str, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Validate a single field value against Tally schema definition."""
        datatype = self.registry.get_datatype(object_type, field_name)
        if not datatype:
            # Field is not in schema or is custom/UDF; assume valid
            return True, None

        if value is None or str(value).strip() == "":
            return True, None

        val_str = str(value).strip()
        dt_lower = datatype.lower()

        if "logical" in dt_lower:
            if val_str.lower() not in ("yes", "no", "true", "false", "1", "0"):
                return False, f"Field '{field_name}' expects Logical ('Yes'/'No'), got '{value}'"

        elif "amount" in dt_lower or "number" in dt_lower:
            try:
                # Remove currency symbols or extra signs
                clean_num = val_str.replace(",", "").replace("$", "").replace("₹", "").strip()
                Decimal(clean_num)
            except Exception:
                return False, f"Field '{field_name}' expects numeric Amount, got '{value}'"

        elif "date" in dt_lower:
            # Check YYYYMMDD, YYYY-MM-DD, or DD-MM-YYYY
            clean_date = val_str.replace("-", "").replace("/", "").replace(".", "")
            if not (len(clean_date) == 8 and clean_date.isdigit()):
                return False, f"Field '{field_name}' expects Date format YYYYMMDD, got '{value}'"

        return True, None

    def validate_voucher_accounting_balance(self, entries: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Validates the fundamental double-entry rule:
        Sum of Debits must exactly equal Sum of Credits.
        """
        total_dr = Decimal("0.00")
        total_cr = Decimal("0.00")

        for idx, entry in enumerate(entries, start=1):
            amount_val = Decimal("0.00")
            try:
                raw_amt = entry.get("amount") or entry.get("debit_amount") or entry.get("credit_amount") or 0
                amount_val = Decimal(str(raw_amt).replace(",", "").strip())
            except Exception:
                return False, f"Entry #{idx} has invalid numeric amount: {entry.get('amount')}"

            entry_type = entry.get("entry_type") or entry.get("type")
            if not entry_type:
                if entry.get("debit_amount") and Decimal(str(entry.get("debit_amount"))) > 0:
                    entry_type = "Debit"
                else:
                    entry_type = "Credit"

            if str(entry_type).lower() in ("debit", "dr"):
                total_dr += abs(amount_val)
            else:
                total_cr += abs(amount_val)

        diff = abs(total_dr - total_cr)
        if diff > Decimal("0.01"):
            return False, f"Accounting unbalanced: Total Debits ({total_dr:.2f}) != Total Credits ({total_cr:.2f}) [Diff: {diff:.2f}]"

        return True, None

    def validate_xml_envelope(self, xml_string: str) -> List[str]:
        """
        Performs full pre-flight validation on an outbound XML envelope before sending to Tally.
        Returns a list of warning/error messages (empty list means 100% valid).
        """
        errors = []
        if not xml_string or not xml_string.strip():
            return ["XML payload is empty"]

        try:
            root = ET.fromstring(xml_string)
        except ET.ParseError as e:
            return [f"Malformed XML syntax: {str(e)}"]

        # Check Envelope Structure
        if root.tag.upper() != "ENVELOPE":
            errors.append(f"Root tag must be <ENVELOPE>, found <{root.tag}>")

        # Check for presence of VOUCHER or LEDGER or other master tags
        vouchers = root.findall(".//VOUCHER")
        ledgers = root.findall(".//LEDGER")
        stock_items = root.findall(".//STOCKITEM")

        for v in vouchers:
            vtype = v.findtext("VOUCHERTYPENAME")
            vdate = v.findtext("DATE")
            vnum = v.findtext("VOUCHERNUMBER")
            if not vtype:
                errors.append("VOUCHER missing mandatory <VOUCHERTYPENAME> tag")
            if not vdate:
                errors.append("VOUCHER missing mandatory <DATE> tag")
            elif len(vdate.strip()) != 8 or not vdate.strip().isdigit():
                errors.append(f"VOUCHER <DATE> '{vdate}' must be in YYYYMMDD format")

            # Check IRN length if present
            irn = v.findtext("IRN")
            if irn and len(irn.strip()) not in (64, 0):
                errors.append(f"IRN length is {len(irn.strip())} chars (expected 64 characters)")

            # Check E-Way Bill Number if present
            for eb in v.findall(".//EWAYBILLDETAILS.LIST"):
                eb_num = eb.findtext("BILLNUMBER")
                if eb_num and len(eb_num.strip()) not in (12, 0):
                    errors.append(f"e-Way Bill number '{eb_num}' length is {len(eb_num.strip())} (standard is 12 digits)")

        for l in ledgers:
            lname = l.findtext("NAME") or l.get("NAME")
            parent = l.findtext("PARENT")
            if not lname:
                errors.append("LEDGER missing mandatory <NAME> tag")
            if not parent:
                errors.append(f"LEDGER '{lname}' missing mandatory <PARENT> group tag")

        return errors
