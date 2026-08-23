from typing import Dict, Any, List, Optional, Union
from decimal import Decimal
from datetime import date, datetime
from app.services.tally_schema_validator import TallySchemaValidator, TallySchemaRegistry

class SchemaXmlBuilder:
    """
    Standardized, schema-aware XML builder for Tally Prime payloads.
    Guarantees proper XML escaping, indentation, formatting, and tag naming.
    """
    def __init__(self, validator: Optional[TallySchemaValidator] = None):
        self.validator = validator or TallySchemaValidator()
        self.registry = self.validator.registry

    def tag(self, tag_name: str, value: Any, default: str = "") -> str:
        """Create a single XML tag with properly escaped content."""
        if value is None:
            if default != "":
                return f"<{tag_name}>{self.validator.escape_xml(default)}</{tag_name}>"
            return ""
        
        if isinstance(value, bool):
            val_str = self.validator.format_logical(value)
        elif isinstance(value, (datetime, date)):
            val_str = self.validator.format_date(value)
        elif isinstance(value, (Decimal, float, int)):
            val_str = self.validator.format_amount(value)
        else:
            val_str = str(value).strip()

        if not val_str and default != "":
            val_str = default

        return f"<{tag_name}>{self.validator.escape_xml(val_str)}</{tag_name}>"

    def collection(self, collection_name: str, items: List[Dict[str, Any]], indent_spaces: int = 4) -> str:
        """
        Build a list of repeated XML elements (e.g. BILLALLOCATIONS.LIST, EWAYBILLDETAILS.LIST).
        """
        if not items:
            return ""
        
        indent = " " * indent_spaces
        child_indent = " " * (indent_spaces + 2)
        out = []
        
        for item in items:
            out.append(f"{indent}<{collection_name}>")
            for k, v in item.items():
                if v is not None and str(v).strip() != "":
                    out.append(f"{child_indent}{self.tag(k, v)}")
            out.append(f"{indent}</{collection_name}>")
            
        return "\n".join(out)

    def wrap_envelope(
        self,
        company_name: str,
        body_xml: str,
        request_type: str = "Import Data",
        report_name: str = "All Masters"
    ) -> str:
        """Wrap body XML inside a standard Tally <ENVELOPE> container."""
        esc_comp = self.validator.escape_xml(company_name)
        return f"""<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>{request_type}</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>{report_name}</REPORTNAME>
        <STATICVARIABLES>
          <SVCURRENTCOMPANY>{esc_comp}</SVCURRENTCOMPANY>
        </STATICVARIABLES>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
{body_xml}
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""
