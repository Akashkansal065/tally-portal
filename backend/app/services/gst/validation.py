"""Pure GST validation helpers shared by API and filing workflows."""

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any, Iterable


GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


@dataclass(frozen=True)
class GstValidationIssue:
    code: str
    field: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
        }


def validate_gstin(value: str | None, field: str = "gstin") -> list[GstValidationIssue]:
    """Validate the format of an Indian GSTIN without calling an external API."""
    if not value:
        return []
    normalized = value.strip().upper()
    if not GSTIN_PATTERN.fullmatch(normalized):
        return [GstValidationIssue("INVALID_GSTIN", field, "GSTIN must be a valid 15-character identifier.")]
    return []


def validate_tax_components(
    taxable_value: Decimal,
    cgst: Decimal = Decimal("0"),
    sgst: Decimal = Decimal("0"),
    igst: Decimal = Decimal("0"),
    cess: Decimal = Decimal("0"),
    *,
    field_prefix: str = "",
) -> list[GstValidationIssue]:
    """Validate non-negative tax values and the basic intra/inter-state split."""
    issues: list[GstValidationIssue] = []
    values = {
        "taxable_value": taxable_value,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "cess_amount": cess,
    }
    for field, value in values.items():
        if value < 0:
            issues.append(GstValidationIssue("NEGATIVE_AMOUNT", f"{field_prefix}{field}", "Amount cannot be negative."))

    if (cgst > 0 or sgst > 0) and igst > 0:
        issues.append(
            GstValidationIssue(
                "MIXED_TAX_SPLIT",
                f"{field_prefix}tax",
                "CGST/SGST and IGST cannot both be populated for the same supply.",
            )
        )
    if (cgst > 0) != (sgst > 0):
        issues.append(
            GstValidationIssue(
                "INCOMPLETE_INTRA_STATE_SPLIT",
                f"{field_prefix}tax",
                "CGST and SGST must be provided together.",
            )
        )
    return issues


def validate_return_lines(lines: Iterable[dict[str, Any]]) -> list[GstValidationIssue]:
    """Validate generated GSTR-1 lines and return structured, actionable issues."""
    issues: list[GstValidationIssue] = []
    for index, line in enumerate(lines):
        prefix = f"lines[{index}]."
        issues.extend(validate_gstin(line.get("party_gstin"), f"{prefix}party_gstin"))
        issues.extend(
            validate_tax_components(
                Decimal(str(line.get("taxable_value") or 0)),
                Decimal(str(line.get("cgst_amount") or 0)),
                Decimal(str(line.get("sgst_amount") or 0)),
                Decimal(str(line.get("igst_amount") or 0)),
                Decimal(str(line.get("cess_amount") or 0)),
                field_prefix=prefix,
            )
        )
        if not line.get("invoice_number"):
            issues.append(GstValidationIssue("MISSING_INVOICE_NUMBER", f"{prefix}invoice_number", "Invoice number is required."))
        if not line.get("place_of_supply"):
            issues.append(GstValidationIssue("MISSING_PLACE_OF_SUPPLY", f"{prefix}place_of_supply", "Place of supply is required."))
    return issues
