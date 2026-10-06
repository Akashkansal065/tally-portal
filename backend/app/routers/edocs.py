"""A sales voucher's e-invoice and e-way bill: what's there, what's missing, and the actions (Phase 4).
Generating the IRN itself stays at POST /gst/einvoice/{voucher_id}/generate (app/routers/gst.py)."""
import random
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.datetime_utils import get_ist_now
from app.core.permissions import require_permission
from app.models.portal_core import Company, EinvoiceMetadata, User
from app.services import einvoicing
from app.services import gst_documents as docs
from app.services.gsp import GspError, einvoice_ready, eway_ready
from app.services.integrations import is_enabled, require_integration

router = APIRouter(prefix="/gst", tags=["GST e-Invoice & e-Way Bill"])


class TransportIn(BaseModel):
    vehicle_no: str = ""
    distance_km: int = Field(0, ge=0, le=4000)
    transporter_id: str = ""
    transporter_name: str = ""
    mode: str = "road"
    doc_no: str = ""
    doc_date: Optional[date] = None

    def to_transport(self) -> docs.Transport:
        return docs.Transport(vehicle_no=self.vehicle_no.strip(), distance_km=self.distance_km,
                              transporter_id=self.transporter_id.strip(), transporter_name=self.transporter_name.strip(),
                              mode=self.mode, doc_no=self.doc_no.strip(), doc_date=self.doc_date)


class CancelIn(BaseModel):
    reason: str
    remark: str = ""


class VehicleIn(TransportIn):
    reason: str = "4"
    remark: str = ""
    from_place: str = ""


async def _company(db: AsyncSession, user: User) -> Company:
    return (await db.execute(select(Company).where(Company.company_id == user.company_id))).scalars().first()


def _fail(e: Exception):
    if isinstance(e, LookupError):
        raise HTTPException(status_code=404, detail="Voucher not found.")
    if isinstance(e, einvoicing.NotReady):
        raise HTTPException(status_code=422, detail={"message": "Fix these first:", "problems": e.problems})
    if isinstance(e, GspError):
        raise HTTPException(status_code=502, detail=f"The GST portal refused it: {e}")
    raise e


async def _demo_record(db: AsyncSession, voucher_id: int) -> Optional[EinvoiceMetadata]:
    return (await db.execute(select(EinvoiceMetadata).where(
        EinvoiceMetadata.voucher_id == voucher_id, EinvoiceMetadata.environment == "mock")
        .order_by(EinvoiceMetadata.metadata_id.desc()))).scalars().first()


@router.get("/edocs/{voucher_id}")
async def voucher_edocs(voucher_id: int, user: User = Depends(require_permission("vouchers", "read")),
                        db: AsyncSession = Depends(get_db)):
    company = await _company(db, user)
    try:
        doc = await docs.load_document(db, user.company_id, voucher_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Voucher not found.")
    live = einvoicing.is_live(company)
    record = await einvoicing.live_record(db, voucher_id) if live else await _demo_record(db, voucher_id)
    now = get_ist_now()
    out = einvoicing.record_out(record)
    return {
        "mode": "live" if live else "demo",
        "is_b2b": bool(doc.party and doc.party.gstin and docs.GSTIN_PATTERN.match(doc.party.gstin)),
        "invoice_total": float(doc.invoice_total),
        "einvoice": {"switch_on": await is_enabled(db, user.company_id, "einvoice"), "keys_ready": einvoice_ready(company),
                     "problems": docs.einvoice_problems(doc)},
        "eway_bill": {"switch_on": await is_enabled(db, user.company_id, "eway_bill"), "keys_ready": eway_ready(company),
                      "problems": [p for p in doc.problems if "GSTIN on" not in p]},
        "record": out,
        "can_cancel_irn": bool(record and record.irn and out["irn_status"] == "active" and out["ewb_status"] != "active"
                               and (not record.ack_date or now - record.ack_date <= einvoicing.CANCEL_WINDOW)),
        "can_cancel_ewb": bool(record and record.eway_bill_no and out["ewb_status"] == "active"
                               and (not record.eway_bill_date or now - record.eway_bill_date <= einvoicing.CANCEL_WINDOW)),
    }


@router.post("/einvoice/{voucher_id}/cancel")
async def cancel_einvoice(voucher_id: int, req: CancelIn, user: User = Depends(require_permission("vouchers", "update")),
                          db: AsyncSession = Depends(get_db), _on: User = Depends(require_integration("einvoice"))):
    company = await _company(db, user)
    if not einvoicing.is_live(company):
        record = await _demo_record(db, voucher_id)
        if not record or not record.irn:
            raise HTTPException(status_code=422, detail="There's no demo e-invoice on this voucher.")
        record.irn_status, record.irn_cancelled_at = "cancelled", get_ist_now()
    else:
        try:
            record = await einvoicing.cancel_irn(db, company, voucher_id, user.user_id, req.reason, req.remark)
        except Exception as e:  # noqa: BLE001 - mapped to HTTP errors
            _fail(e)
    await db.commit()
    return einvoicing.record_out(record)


@router.post("/ewaybill/{voucher_id}/generate")
async def generate_ewaybill(voucher_id: int, req: TransportIn, user: User = Depends(require_permission("vouchers", "update")),
                            db: AsyncSession = Depends(get_db), _on: User = Depends(require_integration("eway_bill"))):
    company = await _company(db, user)
    t = req.to_transport()
    if not einvoicing.is_live(company):
        # Demo: a made-up 12-digit number, labelled demo everywhere, never printed or sent to Tally
        try:
            doc = await docs.load_document(db, user.company_id, voucher_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Voucher not found.")
        problems = docs.ewaybill_problems(doc, t)
        if problems:
            raise HTTPException(status_code=422, detail={"message": "Fix these first:", "problems": problems})
        record = await _demo_record(db, voucher_id) or EinvoiceMetadata(voucher_id=voucher_id, environment="mock")
        record.eway_bill_no = "1" + "".join(str(random.randint(0, 9)) for _ in range(11))
        record.eway_bill_date, record.ewb_status = get_ist_now(), "active"
        db.add(record)
    else:
        try:
            record = await einvoicing.generate_ewaybill(db, company, voucher_id, user.user_id, t)
        except Exception as e:  # noqa: BLE001
            _fail(e)
    await db.commit()
    return einvoicing.record_out(record)


@router.post("/ewaybill/{voucher_id}/vehicle")
async def update_vehicle(voucher_id: int, req: VehicleIn, user: User = Depends(require_permission("vouchers", "update")),
                         db: AsyncSession = Depends(get_db), _on: User = Depends(require_integration("eway_bill"))):
    company = await _company(db, user)
    if not einvoicing.is_live(company):
        raise HTTPException(status_code=422, detail="Vehicle updates need Live mode.")
    try:
        record = await einvoicing.update_vehicle(db, company, voucher_id, user.user_id, vehicle_no=req.vehicle_no,
                                                 reason=req.reason, remark=req.remark, from_place=req.from_place,
                                                 t=req.to_transport())
    except Exception as e:  # noqa: BLE001
        _fail(e)
    await db.commit()
    return einvoicing.record_out(record)


@router.post("/ewaybill/{voucher_id}/cancel")
async def cancel_ewaybill(voucher_id: int, req: CancelIn, user: User = Depends(require_permission("vouchers", "update")),
                          db: AsyncSession = Depends(get_db), _on: User = Depends(require_integration("eway_bill"))):
    company = await _company(db, user)
    if not einvoicing.is_live(company):
        record = await _demo_record(db, voucher_id)
        if not record or not record.eway_bill_no:
            raise HTTPException(status_code=422, detail="There's no demo e-way bill on this voucher.")
        record.ewb_status, record.ewb_cancelled_at = "cancelled", get_ist_now()
    else:
        try:
            record = await einvoicing.cancel_ewaybill(db, company, voucher_id, user.user_id, req.reason, req.remark)
        except Exception as e:  # noqa: BLE001
            _fail(e)
    await db.commit()
    return einvoicing.record_out(record)
