"""Live e-invoices and e-way bills for a sales voucher (Phase 4): checks, sending through the GSP, and storing the
numbers. Records go in einvoice_metadata (environment "live") and are mirrored onto the voucher's own IRN / e-way
bill fields (and trn_eway_bills), which the Tally sync already reads. The demo path stays in app/routers/gst.py.
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import get_ist_now
from app.models.portal_core import AuditLog, Company, EinvoiceMetadata
from app.models.tally_core import TrnEwayBill, TrnVoucher
from app.services import gst_documents as docs
from app.services.gsp import GspError, einvoice_ready, eway_ready, provider

CANCEL_WINDOW = timedelta(hours=24)


class NotReady(Exception):
    """The request can't be sent: problems to fix first (list of plain-language messages)."""

    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def is_live(company: Company) -> bool:
    return (company.einvoice_env or "mock") != "mock"


def parse_when(value) -> Optional[datetime]:
    """IRP: '2026-10-06 11:22:00'; e-way bill API: '06/10/2026 11:22:00 AM'."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


async def live_record(db: AsyncSession, voucher_id: int) -> Optional[EinvoiceMetadata]:
    return (await db.execute(select(EinvoiceMetadata).where(
        EinvoiceMetadata.voucher_id == voucher_id, EinvoiceMetadata.environment == "live")
        .order_by(EinvoiceMetadata.metadata_id.desc()))).scalars().first()


def _audit(db, company_id: int, user_id: int, action: str, voucher_id: int, value: dict) -> None:
    db.add(AuditLog(company_id=company_id, user_id=user_id, action=action[:20], entity_type="Voucher",
                    entity_id=voucher_id, new_value=value))


async def generate_irn(db: AsyncSession, company: Company, voucher_id: int, user_id: int) -> EinvoiceMetadata:
    if not einvoice_ready(company):
        raise NotReady(["e-Invoice keys aren't set: the GSP account on the server and the e-invoice portal API user (Admin → Integrations)."])
    record = await live_record(db, voucher_id)
    if record and record.irn and record.irn_status == "active":
        return record
    doc = await docs.load_document(db, company.company_id, voucher_id)
    problems = docs.einvoice_problems(doc)
    if problems:
        raise NotReady(problems)
    result = await provider().generate_irn(company, docs.einvoice_payload(doc))
    now = get_ist_now()
    record = record or EinvoiceMetadata(voucher_id=voucher_id, environment="live")
    record.irn, record.ack_no = result.get("Irn"), str(result.get("AckNo") or "")[:30] or None
    record.ack_date = parse_when(result.get("AckDt")) or now
    record.signed_qr, record.irn_status, record.irn_cancelled_at = result.get("SignedQRCode"), "active", None
    if result.get("EwbNo"):
        record.eway_bill_no, record.eway_bill_date = str(result["EwbNo"]), parse_when(result.get("EwbDt"))
        record.ewb_valid_till, record.ewb_status = parse_when(result.get("EwbValidTill")), "active"
    record.raw_response = None  # the signed invoice is large and recoverable with get_irn
    db.add(record)
    v = doc.voucher
    v.irn, v.irn_ack_no, v.irn_ack_date = record.irn, record.ack_no, record.ack_date
    v.irn_qr_code, v.irn_source, v.irn_cancelled = record.signed_qr, "MyTally", False
    _audit(db, company.company_id, user_id, "EINVOICE_IRN", voucher_id, {"irn": record.irn, "ack_no": record.ack_no})
    return record


async def cancel_irn(db: AsyncSession, company: Company, voucher_id: int, user_id: int, reason: str, remark: str) -> EinvoiceMetadata:
    record = await live_record(db, voucher_id)
    if not record or not record.irn or record.irn_status != "active":
        raise NotReady(["There's no active e-invoice on this voucher."])
    if reason not in docs.CANCEL_REASONS:
        raise NotReady(["Choose a cancellation reason."])
    if record.ack_date and get_ist_now() - record.ack_date > CANCEL_WINDOW:
        raise NotReady(["An e-invoice can only be cancelled within 24 hours. Issue a credit note instead."])
    if record.ewb_status == "active":
        raise NotReady(["Cancel the e-way bill first."])
    await provider().cancel_irn(company, record.irn, reason, remark or docs.CANCEL_REASONS[reason])
    now = get_ist_now()
    record.irn_status, record.irn_cancelled_at = "cancelled", now
    v = (await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id))).scalars().first()
    if v:
        v.irn_cancelled, v.irn_cancel_date, v.irn_cancel_reason = True, now, docs.CANCEL_REASONS[reason]
    _audit(db, company.company_id, user_id, "EINVOICE_CANCEL", voucher_id, {"irn": record.irn, "reason": reason})
    return record


async def generate_ewaybill(db: AsyncSession, company: Company, voucher_id: int, user_id: int, t: docs.Transport) -> EinvoiceMetadata:
    record = await live_record(db, voucher_id)
    if record and record.eway_bill_no and record.ewb_status == "active":
        return record
    via_irn = bool(record and record.irn and record.irn_status == "active")
    if via_irn and not einvoice_ready(company):
        raise NotReady(["e-Invoice keys aren't set; they're needed to make the e-way bill from the IRN."])
    if not via_irn and not eway_ready(company):
        raise NotReady(["e-Way bill keys aren't set: the GSP account on the server and the e-way bill portal API user (Admin → Integrations)."])
    doc = await docs.load_document(db, company.company_id, voucher_id)
    problems = docs.ewaybill_problems(doc, t)
    if problems:
        raise NotReady(problems)
    if via_irn:
        body = {"Irn": record.irn, "Distance": t.distance_km, "TransMode": docs.TRANSPORT_MODES[t.mode],
                "TransId": t.transporter_id.upper() or None, "TransName": t.transporter_name or None,
                "TransDocNo": t.doc_no or None, "TransDocDt": t.doc_date.strftime("%d/%m/%Y") if t.doc_date else None,
                "VehNo": docs.clean_vehicle(t.vehicle_no) or None, "VehType": "R" if t.vehicle_no else None}
        result = await provider().ewaybill_by_irn(company, {k: v for k, v in body.items() if v is not None})
        number, when, valid = result.get("EwbNo"), result.get("EwbDt"), result.get("EwbValidTill")
    else:
        result = await provider().generate_ewaybill(company, docs.ewaybill_payload(doc, t))
        number, when, valid = result.get("ewayBillNo"), result.get("ewayBillDate"), result.get("validUpto")
    if not number:
        raise GspError("The e-way bill system didn't return a number.")
    record = record or EinvoiceMetadata(voucher_id=voucher_id, environment="live")
    record.eway_bill_no, record.eway_bill_date = str(number), parse_when(when) or get_ist_now()
    record.ewb_valid_till, record.ewb_status, record.ewb_cancelled_at = parse_when(valid), "active", None
    db.add(record)
    v = doc.voucher
    v.eway_bill_no, v.vehicle_no = record.eway_bill_no, docs.clean_vehicle(t.vehicle_no) or v.vehicle_no
    db.add(TrnEwayBill(voucher_id=voucher_id, bill_number=record.eway_bill_no,
                       bill_date=record.eway_bill_date.date() if record.eway_bill_date else None,
                       valid_up_to=record.ewb_valid_till, distance_km=t.distance_km or None,
                       transporter_id=t.transporter_id.upper() or None, transporter_name=t.transporter_name or None,
                       doc_number=t.doc_no or None, doc_date=t.doc_date, vehicle_number=docs.clean_vehicle(t.vehicle_no) or None,
                       transport_mode=t.mode.title(), status="ACTIVE"))
    _audit(db, company.company_id, user_id, "EWAYBILL", voucher_id, {"ewb_no": record.eway_bill_no, "via_irn": via_irn})
    return record


async def _active_ewb(db: AsyncSession, voucher_id: int) -> EinvoiceMetadata:
    record = await live_record(db, voucher_id)
    if not record or not record.eway_bill_no or record.ewb_status != "active":
        raise NotReady(["There's no active e-way bill on this voucher."])
    return record


async def update_vehicle(db: AsyncSession, company: Company, voucher_id: int, user_id: int, *, vehicle_no: str,
                         reason: str, remark: str, from_place: str, t: docs.Transport) -> EinvoiceMetadata:
    record = await _active_ewb(db, voucher_id)
    if not eway_ready(company):
        raise NotReady(["e-Way bill keys aren't set (Admin → Integrations)."])
    vehicle = docs.clean_vehicle(vehicle_no)
    problems = []
    if not docs.VEHICLE_PATTERN.match(vehicle):
        problems.append(f"{vehicle_no or 'That'} doesn't look like a vehicle number (e.g. UP15AB1234).")
    if reason not in docs.VEHICLE_REASONS:
        problems.append("Choose why the vehicle is changing.")
    if not from_place.strip():
        problems.append("Enter where the goods are now (place).")
    if problems:
        raise NotReady(problems)
    state = docs.state_code(company.gstin, company.state)
    result = await provider().update_vehicle(company, {
        "ewbNo": int(record.eway_bill_no), "vehicleNo": vehicle, "fromPlace": from_place[:50], "fromState": int(state or 0),
        "reasonCode": reason, "reasonRem": (remark or docs.VEHICLE_REASONS[reason])[:50],
        "transDocNo": t.doc_no[:15], "transDocDate": t.doc_date.strftime("%d/%m/%Y") if t.doc_date else "",
        "transMode": docs.TRANSPORT_MODES.get(t.mode, "1"), "vehicleType": "R",
    })
    record.ewb_valid_till = parse_when(result.get("validUpto")) or record.ewb_valid_till
    v = (await db.execute(select(TrnVoucher).where(TrnVoucher.voucher_id == voucher_id))).scalars().first()
    if v:
        v.vehicle_no = vehicle
    _audit(db, company.company_id, user_id, "EWAYBILL_VEHICLE", voucher_id, {"ewb_no": record.eway_bill_no, "vehicle": vehicle})
    return record


async def cancel_ewaybill(db: AsyncSession, company: Company, voucher_id: int, user_id: int, reason: str, remark: str) -> EinvoiceMetadata:
    record = await _active_ewb(db, voucher_id)
    if reason not in docs.EWB_CANCEL_REASONS:
        raise NotReady(["Choose a cancellation reason."])
    if record.eway_bill_date and get_ist_now() - record.eway_bill_date > CANCEL_WINDOW:
        raise NotReady(["An e-way bill can only be cancelled within 24 hours of making it."])
    if not eway_ready(company):
        raise NotReady(["e-Way bill keys aren't set (Admin → Integrations)."])
    await provider().cancel_ewaybill(company, record.eway_bill_no, reason, remark or docs.EWB_CANCEL_REASONS[reason])
    now = get_ist_now()
    record.ewb_status, record.ewb_cancelled_at = "cancelled", now
    rows = (await db.execute(select(TrnEwayBill).where(TrnEwayBill.voucher_id == voucher_id,
                                                       TrnEwayBill.bill_number == record.eway_bill_no))).scalars().all()
    for row in rows:
        row.status = "CANCELLED"
    _audit(db, company.company_id, user_id, "EWAYBILL_CANCEL", voucher_id, {"ewb_no": record.eway_bill_no, "reason": reason})
    return record


def record_out(record: Optional[EinvoiceMetadata]) -> Optional[dict]:
    if record is None:
        return None
    return {
        "environment": record.environment, "demo": record.environment == "mock",
        "irn": record.irn, "ack_no": record.ack_no, "ack_date": record.ack_date.isoformat() if record.ack_date else None,
        "irn_status": record.irn_status or ("active" if record.irn else None), "signed_qr": record.signed_qr,
        "eway_bill_no": record.eway_bill_no,
        "eway_bill_date": record.eway_bill_date.isoformat() if record.eway_bill_date else None,
        "ewb_valid_till": record.ewb_valid_till.isoformat() if record.ewb_valid_till else None,
        "ewb_status": record.ewb_status or ("active" if record.eway_bill_no else None),
    }
