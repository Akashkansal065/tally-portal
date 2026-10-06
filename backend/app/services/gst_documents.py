"""e-Invoice (IRN) and e-Way bill request bodies built from a Tally sales voucher, with plain-language checks.

The e-invoice body follows the government's INV-01 schema (version 1.1); the e-way bill body follows the NIC
e-way bill API (version 1.03). Both are provider-neutral: app/services/gsp.py sends them through the GST
Suvidha Provider. Amounts come from the voucher's stock lines (taxable value) and the stock items' GST rates;
the invoice total is the party's debit, and any difference becomes round-off / other charges / discount.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.portal_core import Company
from app.models.tally_core import MstLedger, MstStockItem, TrnAccounting, TrnInventory, TrnVoucher

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")

STATE_CODES: Dict[str, str] = {
    "jammu and kashmir": "01", "jammu & kashmir": "01", "himachal pradesh": "02", "punjab": "03", "chandigarh": "04",
    "uttarakhand": "05", "haryana": "06", "delhi": "07", "rajasthan": "08", "uttar pradesh": "09", "bihar": "10",
    "sikkim": "11", "arunachal pradesh": "12", "nagaland": "13", "manipur": "14", "mizoram": "15", "tripura": "16",
    "meghalaya": "17", "assam": "18", "west bengal": "19", "jharkhand": "20", "odisha": "21", "chhattisgarh": "22",
    "madhya pradesh": "23", "gujarat": "24", "dadra and nagar haveli and daman and diu": "26",
    "daman and diu": "26", "dadra and nagar haveli": "26", "maharashtra": "27", "karnataka": "29", "goa": "30",
    "lakshadweep": "31", "kerala": "32", "tamil nadu": "33", "puducherry": "34", "andaman and nicobar islands": "35",
    "telangana": "36", "andhra pradesh": "37", "ladakh": "38",
}

# Tally unit symbols → GST unit quantity codes (UQC); anything else is OTH
UNIT_CODES = {
    "pcs": "PCS", "pc": "PCS", "piece": "PCS", "pieces": "PCS", "nos": "NOS", "no": "NOS", "number": "NOS",
    "kg": "KGS", "kgs": "KGS", "kilogram": "KGS", "gm": "GMS", "gms": "GMS", "g": "GMS", "ltr": "LTR", "l": "LTR",
    "litre": "LTR", "ml": "MLT", "mtr": "MTR", "m": "MTR", "box": "BOX", "boxes": "BOX", "set": "SET", "sets": "SET",
    "doz": "DOZ", "dozen": "DOZ", "pkt": "PAC", "pac": "PAC", "pack": "PAC", "packet": "PAC", "bag": "BAG",
    "btl": "BTL", "bottle": "BTL", "ctn": "CTN", "carton": "CTN", "pair": "PRS", "prs": "PRS", "roll": "ROL",
    "rol": "ROL", "sqm": "SQM", "sqf": "SQF", "sqft": "SQF", "tin": "TIN", "unit": "UNT", "units": "UNT",
}

CANCEL_REASONS = {"1": "Duplicate", "2": "Data entry mistake", "3": "Order cancelled", "4": "Others"}
EWB_CANCEL_REASONS = {"1": "Duplicate", "2": "Order cancelled", "3": "Data entry mistake", "4": "Others"}
VEHICLE_REASONS = {"1": "Breakdown", "2": "Transhipment", "3": "Others", "4": "First time"}
TRANSPORT_MODES = {"road": "1", "rail": "2", "air": "3", "ship": "4"}
VEHICLE_PATTERN = re.compile(r"^[A-Z]{2}[0-9A-Z]{1,3}[A-Z]{0,3}[0-9]{4}$|^TMP[0-9A-Z]{4,12}$")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def state_code(gstin: Optional[str], state: Optional[str]) -> Optional[str]:
    if gstin and GSTIN_PATTERN.match(gstin):
        return gstin[:2]
    return STATE_CODES.get((state or "").strip().lower())


def clean_pin(value: Optional[str]) -> Optional[int]:
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if len(digits) == 6 and digits[0] != "0" else None


def clean_vehicle(value: Optional[str]) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def split_address(text: Optional[str]) -> List[str]:
    """Up to two lines of at most 100 characters (the schema's limit), split at commas."""
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) <= 100:
        return [text] if text else []
    cut = text.rfind(",", 0, 100)
    cut = cut if cut > 20 else 100
    return [text[:cut].strip(" ,"), text[cut:].strip(" ,")[:100]]


@dataclass
class Line:
    name: str
    hsn: Optional[str]
    unit: str
    quantity: Decimal
    rate: Decimal
    gross: Decimal  # before line discount
    discount: Decimal
    taxable: Decimal
    gst_rate: Decimal
    cgst: Decimal = Decimal("0")
    sgst: Decimal = Decimal("0")
    igst: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.taxable + self.cgst + self.sgst + self.igst


@dataclass
class Document:
    """Everything both requests need, gathered once from the voucher, with the problems found."""
    voucher: TrnVoucher
    company: Company
    party: Optional[MstLedger]
    lines: List[Line] = field(default_factory=list)
    inter_state: bool = False
    seller_state: Optional[str] = None
    buyer_state: Optional[str] = None
    invoice_total: Decimal = Decimal("0")
    round_off: Decimal = Decimal("0")
    other_charges: Decimal = Decimal("0")
    discount: Decimal = Decimal("0")
    problems: List[str] = field(default_factory=list)

    @property
    def taxable(self) -> Decimal:
        return sum((l.taxable for l in self.lines), Decimal("0"))

    def tax(self, kind: str) -> Decimal:
        return sum((getattr(l, kind) for l in self.lines), Decimal("0"))

    @property
    def doc_date(self) -> str:
        return self.voucher.voucher_date.strftime("%d/%m/%Y")


async def load_document(db: AsyncSession, company_id: int, voucher_id: int) -> Document:
    voucher = (await db.execute(
        select(TrnVoucher)
        .options(selectinload(TrnVoucher.voucher_type),
                 selectinload(TrnVoucher.entries).selectinload(TrnAccounting.ledger).selectinload(MstLedger.group),
                 selectinload(TrnVoucher.inventory_entries).selectinload(TrnInventory.stock_item).selectinload(MstStockItem.unit))
        .where(TrnVoucher.voucher_id == voucher_id, TrnVoucher.company_id == company_id))).scalars().first()
    if voucher is None:
        raise LookupError("Voucher not found.")
    company = (await db.execute(select(Company).where(Company.company_id == company_id))).scalars().first()
    from app.routers.vouchers import _resolve_party_and_amount
    _, party_amount, party_ledger_id = _resolve_party_and_amount(voucher.entries)
    party_ledger_id = voucher.party_ledger_id or party_ledger_id
    party = next((e.ledger for e in voucher.entries if e.ledger and e.ledger_id == party_ledger_id), None)
    doc = Document(voucher=voucher, company=company, party=party)
    check_and_compute(doc, money(party_amount or voucher.total_amount))
    return doc


def check_and_compute(doc: Document, party_total: Decimal) -> None:
    v, company, party = doc.voucher, doc.company, doc.party
    problems = doc.problems
    vtype = (v.voucher_type.name if v.voucher_type else "") + " " + (v.voucher_type.parent_type if v.voucher_type else "")
    if "sales" not in vtype.lower():
        problems.append("Only sales vouchers can have an e-invoice or e-way bill.")
    if v.is_cancelled:
        problems.append("This voucher is cancelled.")

    if not company.gstin or not GSTIN_PATTERN.match(company.gstin):
        problems.append("The company GSTIN isn't set (Company profile).")
    doc.seller_state = state_code(company.gstin, company.state)
    if not company.address_line1:
        problems.append("The company address isn't set (Company profile).")
    if not clean_pin(company.pincode):
        problems.append("The company pincode isn't set (Company profile).")
    if not doc.seller_state:
        problems.append("The company state isn't set (Company profile).")

    if party is None:
        problems.append("The voucher has no party (customer) ledger.")
    else:
        doc.buyer_state = state_code(party.gstin, party.state)
        if party.gstin and not GSTIN_PATTERN.match(party.gstin):
            problems.append(f"The GSTIN on {party.name}'s ledger looks wrong: {party.gstin}.")
        if not clean_pin(party.pincode):
            problems.append(f"{party.name}'s ledger has no pincode (set it in Tally).")
        if not (party.address or "").strip():
            problems.append(f"{party.name}'s ledger has no address (set it in Tally).")
        if not doc.buyer_state:
            problems.append(f"{party.name}'s ledger has no state (set it in Tally).")
    doc.inter_state = bool(doc.seller_state and doc.buyer_state and doc.seller_state != doc.buyer_state)

    items = [i for i in (v.inventory_entries or []) if not i.is_inward]
    if not items:
        problems.append("The voucher has no stock items; e-invoice and e-way bill need item lines with HSN codes.")
    for i in items:
        item = i.stock_item
        name = (item.name if item else None) or "Item"
        hsn = re.sub(r"\D", "", (item.hsn_code if item else "") or "")
        if len(hsn) not in (4, 6, 8):
            problems.append(f"{name} has no valid HSN code (set it on the stock item in Tally).")
        quantity = abs(Decimal(str(i.billed_qty or i.quantity or 0)))
        taxable = abs(money(i.amount))
        discount = abs(money(i.discount_amount))
        rate = abs(money(i.rate))
        gst_rate = Decimal(str(item.gst_rate_percent or 0)) if item else Decimal("0")
        symbol = ((item.unit.symbol if item and item.unit else "") or "").strip().lower().rstrip(".")
        line = Line(name=name[:300], hsn=hsn or None, unit=UNIT_CODES.get(symbol, "OTH"), quantity=quantity, rate=rate,
                    gross=taxable + discount, discount=discount, taxable=taxable, gst_rate=gst_rate)
        tax = money(taxable * gst_rate / 100)
        if doc.inter_state:
            line.igst = tax
        else:
            line.cgst = money(tax / 2)
            line.sgst = tax - line.cgst
        doc.lines.append(line)

    doc.invoice_total = party_total
    round_off = Decimal("0")
    for e in v.entries or []:
        name = (e.ledger.name if e.ledger else "").lower()
        if "round" in name:
            round_off += money(e.credit_amount) - money(e.debit_amount)
    doc.round_off = round_off
    remainder = party_total - doc.taxable - doc.tax("cgst") - doc.tax("sgst") - doc.tax("igst") - round_off
    if remainder > Decimal("0.99"):
        doc.other_charges = remainder
    elif remainder < Decimal("-0.99"):
        doc.discount = -remainder
    else:
        doc.round_off += remainder  # paise differences from rounding each line


def _seller(doc: Document) -> dict:
    c = doc.company
    lines = split_address(", ".join(x for x in (c.address_line1, c.address_line2) if x))
    seller = {"Gstin": c.gstin, "LglNm": c.name[:100], "TrdNm": c.name[:100], "Addr1": (lines or ["-"])[0],
              "Loc": (c.address_line2 or c.state or "-")[:50], "Pin": clean_pin(c.pincode), "Stcd": doc.seller_state}
    if len(lines) > 1:
        seller["Addr2"] = lines[1]
    phone = re.sub(r"\D", "", c.mobile or c.telephone or "")[-12:]
    if len(phone) >= 6:
        seller["Ph"] = phone
    if c.email:
        seller["Em"] = c.email[:100]
    return seller


def einvoice_payload(doc: Document) -> dict:
    """INV-01 (v1.1) body for one B2B tax invoice."""
    v, p = doc.voucher, doc.party
    lines = split_address(p.address)
    buyer = {"Gstin": p.gstin, "LglNm": p.name[:100], "TrdNm": p.name[:100], "Pos": doc.buyer_state,
             "Addr1": (lines or ["-"])[0], "Loc": (p.state or "-")[:50], "Pin": clean_pin(p.pincode), "Stcd": doc.buyer_state}
    if len(lines) > 1:
        buyer["Addr2"] = lines[1]
    phone = re.sub(r"\D", "", p.mobile or p.phone or "")[-12:]
    if len(phone) >= 6:
        buyer["Ph"] = phone
    items = [{
        "SlNo": str(n), "PrdDesc": l.name, "IsServc": "N", "HsnCd": l.hsn, "Qty": float(l.quantity), "Unit": l.unit,
        "UnitPrice": float(l.rate), "TotAmt": float(l.gross), "Discount": float(l.discount), "AssAmt": float(l.taxable),
        "GstRt": float(l.gst_rate), "IgstAmt": float(l.igst), "CgstAmt": float(l.cgst), "SgstAmt": float(l.sgst),
        "CesRt": 0, "CesAmt": 0, "CesNonAdvlAmt": 0, "StateCesRt": 0, "StateCesAmt": 0, "StateCesNonAdvlAmt": 0,
        "OthChrg": 0, "TotItemVal": float(l.total),
    } for n, l in enumerate(doc.lines, start=1)]
    return {
        "Version": "1.1",
        "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N", "IgstOnIntra": "N"},
        "DocDtls": {"Typ": "INV", "No": str(v.voucher_number)[:16], "Dt": doc.doc_date},
        "SellerDtls": _seller(doc),
        "BuyerDtls": buyer,
        "ItemList": items,
        "ValDtls": {
            "AssVal": float(doc.taxable), "CgstVal": float(doc.tax("cgst")), "SgstVal": float(doc.tax("sgst")),
            "IgstVal": float(doc.tax("igst")), "CesVal": 0, "StCesVal": 0, "Discount": float(doc.discount),
            "OthChrg": float(doc.other_charges), "RndOffAmt": float(doc.round_off), "TotInvVal": float(doc.invoice_total),
        },
    }


@dataclass
class Transport:
    vehicle_no: str = ""
    distance_km: int = 0  # 0: the e-way bill system works it out from the two pincodes
    transporter_id: str = ""
    transporter_name: str = ""
    mode: str = "road"
    doc_no: str = ""
    doc_date: Optional[date] = None

    def check(self, part_a_only_ok: bool = True) -> List[str]:
        problems = []
        if self.mode not in TRANSPORT_MODES:
            problems.append("Transport mode must be road, rail, air or ship.")
        if self.vehicle_no and not VEHICLE_PATTERN.match(clean_vehicle(self.vehicle_no)):
            problems.append(f"{self.vehicle_no} doesn't look like a vehicle number (e.g. UP15AB1234).")
        if not self.vehicle_no and not self.transporter_id and not part_a_only_ok:
            problems.append("Enter a vehicle number or a transporter ID.")
        if self.mode == "road" and not self.vehicle_no and not self.transporter_id:
            problems.append("For road transport, enter the vehicle number (or a transporter ID to add it later).")
        if self.transporter_id and not GSTIN_PATTERN.match(self.transporter_id.upper()) and not re.match(r"^\d{2}[A-Z0-9]{13}$", self.transporter_id.upper()):
            problems.append("The transporter ID should be the transporter's GSTIN or 15-character enrolment ID.")
        if not (0 <= self.distance_km <= 4000):
            problems.append("Distance must be between 0 and 4000 km (0 lets the system work it out).")
        return problems


def ewaybill_payload(doc: Document, t: Transport) -> dict:
    """NIC e-way bill API (v1.03) body for an outward supply against a tax invoice."""
    c, p = doc.company, doc.party
    from_lines = split_address(", ".join(x for x in (c.address_line1, c.address_line2) if x))
    to_lines = split_address(p.address)
    body = {
        "supplyType": "O", "subSupplyType": "1", "subSupplyDesc": "", "docType": "INV",
        "docNo": str(doc.voucher.voucher_number)[:16], "docDate": doc.doc_date,
        "fromGstin": c.gstin, "fromTrdName": c.name[:100], "fromAddr1": (from_lines or [""])[0],
        "fromAddr2": from_lines[1] if len(from_lines) > 1 else "", "fromPlace": (c.address_line2 or c.state or "")[:50],
        "fromPincode": clean_pin(c.pincode), "fromStateCode": int(doc.seller_state), "actFromStateCode": int(doc.seller_state),
        "toGstin": p.gstin if p.gstin and GSTIN_PATTERN.match(p.gstin) else "URP", "toTrdName": p.name[:100],
        "toAddr1": (to_lines or [""])[0], "toAddr2": to_lines[1] if len(to_lines) > 1 else "",
        "toPlace": (p.state or "")[:50], "toPincode": clean_pin(p.pincode),
        "toStateCode": int(doc.buyer_state), "actToStateCode": int(doc.buyer_state),
        "transactionType": 1, "otherValue": float(doc.other_charges - doc.discount + doc.round_off),
        "totalValue": float(doc.taxable), "cgstValue": float(doc.tax("cgst")), "sgstValue": float(doc.tax("sgst")),
        "igstValue": float(doc.tax("igst")), "cessValue": 0, "cessNonAdvolValue": 0, "totInvValue": float(doc.invoice_total),
        "transporterId": t.transporter_id.upper(), "transporterName": t.transporter_name[:100],
        "transDocNo": t.doc_no[:15], "transMode": TRANSPORT_MODES[t.mode], "transDistance": str(t.distance_km),
        "transDocDate": t.doc_date.strftime("%d/%m/%Y") if t.doc_date else "",
        "vehicleNo": clean_vehicle(t.vehicle_no), "vehicleType": "R" if t.vehicle_no else "",
        "itemList": [{
            "productName": l.name[:100], "productDesc": l.name[:100], "hsnCode": int(l.hsn) if l.hsn else 0,
            "quantity": float(l.quantity), "qtyUnit": l.unit, "taxableAmount": float(l.taxable),
            "sgstRate": float(l.gst_rate / 2) if not doc.inter_state else 0, "cgstRate": float(l.gst_rate / 2) if not doc.inter_state else 0,
            "igstRate": float(l.gst_rate) if doc.inter_state else 0, "cessRate": 0, "cessNonadvol": 0,
        } for l in doc.lines],
    }
    return body


def ewaybill_problems(doc: Document, t: Transport) -> List[str]:
    """e-Way bill doesn't need the buyer's GSTIN (unregistered buyers are "URP"); the rest of the checks apply."""
    problems = [p for p in doc.problems if "GSTIN on" not in p] + t.check()
    return problems


def einvoice_problems(doc: Document) -> List[str]:
    problems = list(doc.problems)
    if doc.party is not None and not (doc.party.gstin and GSTIN_PATTERN.match(doc.party.gstin)):
        problems.append(f"{doc.party.name} has no GSTIN: e-invoices are only for registered (B2B) buyers.")
    return problems
