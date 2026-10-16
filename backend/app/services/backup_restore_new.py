"""Restore a backup into a NEW MyTally company (WS-13). Server side: the archive's objects are imported, in
dependency order, into a company made for the purpose; nothing is sent to Tally and no existing company is
touched.

  1. the target is a brand-new company and is checked to hold nothing;
  2. every kind is written in ENTITY_ORDER, in batches, through the same importer the sync uses;
  3. the counts in the new company are checked against the manifest (vouchers exactly, masters at least: the
     importer may add a default group or unit of its own);
  4. only after that is the company bound to the backup's Tally company GUID, and only when no other company of the
     account already holds that GUID. A restore that fails verification leaves the new company inactive and
     unbound, with the reason.
"""
import zipfile
from datetime import date
from typing import Any, Dict, List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.portal_core import AuditLog, Company, CompanyBackup, Currency, UserCompanyAccess
from app.models.tally_core import (
    MstAttendanceType, MstCostCategory, MstCostCentre, MstGodown, MstGroup, MstLedger, MstStockCategory,
    MstStockGroup, MstStockItem, MstUom, MstVoucherType, TrnVoucher)
from app.services import backup_archive as archive
from app.services import backups as backup_svc
from app.services.tally_xml_importer import import_tally_xml

logger = get_logger("app.services.backup_restore_new")

BATCH = 100
COUNT_MODELS = {
    "groups": MstGroup, "currencies": Currency, "ledgers": MstLedger, "cost_categories": MstCostCategory,
    "cost_centres": MstCostCentre, "units": MstUom, "attendance_types": MstAttendanceType,
    "stock_groups": MstStockGroup, "stock_categories": MstStockCategory, "godowns": MstGodown,
    "stock_items": MstStockItem, "voucher_types": MstVoucherType, "vouchers": TrnVoucher,
}
EXACT = {"vouchers"}


class RestoreRefused(Exception):
    pass


async def company_counts(db: AsyncSession, company_id: int) -> Dict[str, int]:
    return {key: int((await db.execute(select(func.count()).select_from(model).where(
        model.company_id == company_id))).scalar() or 0) for key, model in COUNT_MODELS.items()}


async def assert_empty(db: AsyncSession, company_id: int) -> None:
    counts = await company_counts(db, company_id)
    held = {k: v for k, v in counts.items() if v and k not in ("currencies", "groups", "units", "voucher_types")}
    if held:
        raise RestoreRefused(f"The target company is not empty ({held}); a restore only writes into an empty company.")


def _envelope(blocks: List[str]) -> str:
    return "<ENVELOPE><BODY><DATA><COLLECTION>" + "".join(blocks) + "</COLLECTION></DATA></BODY></ENVELOPE>"


def _books_from(manifest: Dict[str, Any]) -> date:
    text = str((manifest.get("company") or {}).get("books_from") or "")
    try:
        return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
    except (ValueError, IndexError):
        return date(date.today().year if date.today().month >= 4 else date.today().year - 1, 4, 1)


async def restore_into_new_company(db: AsyncSession, backup: CompanyBackup, source_company: Company, user_id: int,
                                   new_name: str) -> Dict[str, Any]:
    """Make a new company from a stored backup. Returns {company_id, verified, bound, counts, problems}."""
    if backup.status != "stored":
        raise RestoreRefused("Only a stored backup can be restored.")
    try:
        with backup_svc.plaintext_file(backup) as path:
            # The whole archive is checked against its manifest before anything is written
            archive.validate_archive(path)
            with zipfile.ZipFile(path) as zf:
                manifest = archive.read_manifest(zf)
                source_guid = ((manifest.get("company") or {}).get("guid") or "").strip()
                if source_guid and source_company.tally_guid and source_guid != source_company.tally_guid:
                    raise RestoreRefused("This backup is of a different Tally company than the one it is listed under.")

                company = Company(account_id=source_company.account_id, name=new_name.strip()[:150],
                                  books_begin_date=_books_from(manifest), is_active=False,
                                  base_currency=source_company.base_currency)
                db.add(company)
                await db.flush()
                db.add(UserCompanyAccess(user_id=user_id, company_id=company.company_id))
                await db.flush()
                await assert_empty(db, company.company_id)
                await db.commit()

                problems: List[str] = []
                for key, tag in archive.ENTITY_ORDER:
                    blocks = archive.entity_blocks(zf, manifest, key, tag)
                    for start in range(0, len(blocks), BATCH):
                        result = await import_tally_xml(_envelope(blocks[start:start + BATCH]), db, user_id,
                                                        target_company_id=company.company_id, force_overwrite=True)
                        if result.get("status") == "error":
                            problems.append(f"{key}: {str(result.get('message'))[:200]}")
                            break
                        for err in (result.get("errors") or [])[:3]:
                            problems.append(f"{key}: {str(err)[:200]}")
                    await db.commit()
    except archive.ArchiveError as e:
        raise RestoreRefused(str(e))
    except zipfile.BadZipFile:
        raise RestoreRefused("The backup file is not a ZIP archive.")

    counts = await company_counts(db, company.company_id)
    mismatches = []
    for key, _ in archive.ENTITY_ORDER:
        expected = int(manifest["records"].get(key, 0) or 0)
        got = counts.get(key, 0)
        if (got != expected) if key in EXACT else (got < expected):
            mismatches.append(f"{key}: backup holds {expected}, restored {got}")
    verified = not mismatches and not problems

    bound = False
    if verified:
        fingerprint = (manifest.get("company") or {}).get("fingerprint") or None
        taken = None
        if source_guid:
            taken = (await db.execute(select(Company.company_id).where(
                Company.account_id == source_company.account_id, Company.tally_guid == source_guid,
                Company.company_id != company.company_id))).scalars().first()
        if source_guid and taken is None:
            company.tally_guid, company.tally_fingerprint = source_guid, fingerprint
            bound = True
        company.is_active = True
    db.add(AuditLog(company_id=source_company.company_id, user_id=user_id, action="BACKUP_RESTORED_TO_NEW_COMPANY",
                    entity_type="CompanyBackup", entity_id=backup.backup_id,
                    new_value={"new_company_id": company.company_id, "verified": verified, "bound": bound,
                               "mismatches": mismatches[:10]}))
    await db.commit()
    return {"company_id": company.company_id, "name": company.name, "verified": verified, "bound": bound,
            "counts": counts, "manifest_counts": manifest["records"], "problems": (problems + mismatches)[:20]}
