import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

# XML 1.0 valid chars: #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
# Regex matches all invalid control characters (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F, 0x7F-0x84, 0x86-0x9F)
_INVALID_XML_10_CHARS = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]"
)


def clean_xml_str(text: Any) -> str:
    """
    Remove invalid XML 1.0 control characters and return clean string.
    Leaves newlines, tabs, and carriage returns intact.
    """
    if text is None:
        return ""
    return _INVALID_XML_10_CHARS.sub("", str(text))


def x(value: Any) -> str:
    """
    Sanitize and escape any value for safe insertion into Tally XML element content
    or XML attribute values.

    1. Handles None -> ""
    2. Handles bool -> "Yes" / "No"
    3. Handles date/datetime -> "YYYYMMDD"
    4. Handles numbers -> str
    5. Strips XML 1.0 invalid control characters (null bytes, bell, backspace, etc.)
    6. Escapes standard XML entities: &, <, >, ", '
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (datetime, date)):
        return value.strftime("%Y%m%d")
    if isinstance(value, (Decimal, float, int)):
        return str(value)

    # Convert to string and strip invalid control characters
    s = _INVALID_XML_10_CHARS.sub("", str(value))

    # Escape XML entities (note: & must be escaped first)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def xml_tag(tag_name: str, value: Any, default: str = "") -> str:
    """
    Construct a single XML element: <TAG>escaped_value</TAG>.
    If value is None or empty string and default is provided, default is used.
    If value is None or empty string and no default, returns empty string.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        if default:
            return f"<{tag_name}>{x(default)}</{tag_name}>"
        return ""
    return f"<{tag_name}>{x(value)}</{tag_name}>"


def wrap_tally_import_envelope(
    company_name: str,
    message_content: str,
    report_name: str = "All Masters",
    vch_format: str = "XML",
) -> str:
    """
    Wrap payload in standard Tally Prime Import Data envelope with properly escaped company name.
    """
    esc_company = x(company_name)
    return f"""<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Import</TALLYREQUEST>
    <TYPE>Data</TYPE>
    <ID>{x(report_name)}</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVVCHIMPORTFORMAT>{vch_format}</SVVCHIMPORTFORMAT>
        <SVCURRENTCOMPANY>{esc_company}</SVCURRENTCOMPANY>
      </STATICVARIABLES>
    </DESC>
    <DATA>
      <TALLYMESSAGE xmlns:UDF="TallyUDF">
{message_content}
      </TALLYMESSAGE>
    </DATA>
  </BODY>
</ENVELOPE>"""
