"""Admin → Integrations: on/off switches for features that need another provider's keys or a paid subscription."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_current_user
from app.models.portal_core import AuditLog, User
from app.routers.admin import require_admin
from app.services import integrations as svc

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class IntegrationStatus(BaseModel):
    key: str
    label: str
    description: str
    provider: str
    cost: str
    phase: str
    live: bool
    enabled: bool
    status: str


class IntegrationUpdate(BaseModel):
    enabled: bool


@router.get("", response_model=List[IntegrationStatus])
async def list_integrations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Every switch for the user's company. Readable by everyone signed in, so screens know what to show."""
    return await svc.integration_statuses(db, user.company_id)


@router.put("/{key}", response_model=IntegrationStatus)
async def update_integration(
    key: str,
    req: IntegrationUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        row = await svc.set_enabled(db, user.company_id, key, req.enabled, user.user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown integration.")
    await db.flush()
    db.add(AuditLog(company_id=user.company_id, user_id=user.user_id, action="INTEGRATION_ON" if req.enabled else "INTEGRATION_OFF",
                    entity_type="Integration", entity_id=row.id, new_value={"key": key, "enabled": req.enabled}))
    await db.commit()
    return next(s for s in await svc.integration_statuses(db, user.company_id) if s["key"] == key)
