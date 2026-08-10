import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.database import get_db
from app.models.tally_core import MstCostCategory, MstCostCentre, MstCostCentreClass, MstCostCentreClassAllocation
from app.schemas.masters import (
    CostCategoryCreate, CostCategoryUpdate, CostCategoryResponse,
    CostCentreCreate, CostCentreUpdate, CostCentreResponse, CostCentreTreeNode,
    CostCentreClassCreate, CostCentreClassUpdate, CostCentreClassResponse, CostCentreClassAllocationResponse
)
from app.core.permissions import require_permission
from app.models.portal_core import User, SyncQueue
from app.routers.sync import try_push_cost_category_realtime, try_push_cost_centre_realtime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/masters",
    tags=["Accounting Masters"]
)

# ==========================================
# Cost Categories
# ==========================================

@router.get("/cost-categories", response_model=List[CostCategoryResponse])
async def list_cost_categories(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} fetching list of cost categories for company {user.company_id}")
    result = await db.execute(
        select(MstCostCategory)
        .where(MstCostCategory.company_id == user.company_id)
        .order_by(MstCostCategory.name)
    )
    return result.scalars().all()

@router.post("/cost-categories", response_model=CostCategoryResponse)
async def create_cost_category(
    payload: CostCategoryCreate,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    # Check if exists
    result = await db.execute(
        select(MstCostCategory)
        .where(MstCostCategory.company_id == user.company_id, MstCostCategory.name == payload.name)
    )
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Cost Category with this name already exists.")

    new_cc = MstCostCategory(
        company_id=user.company_id,
        name=payload.name,
        alias=payload.alias,
        allocate_revenue=payload.allocate_revenue,
        allocate_non_revenue=payload.allocate_non_revenue,
        is_active=payload.is_active
    )
    db.add(new_cc)
    await db.flush()
    
    new_sq = SyncQueue(company_id=new_cc.company_id, record_type="CostCategory", record_id=new_cc.category_id, action="Create", is_processed=False)
    db.add(new_sq)
    await db.commit()
    await db.refresh(new_cc)
    
    await try_push_cost_category_realtime(new_cc.category_id, new_sq.sync_id, "Create", db)

    return new_cc

@router.put("/cost-categories/{category_id}", response_model=CostCategoryResponse)
async def update_cost_category(
    category_id: int,
    payload: CostCategoryUpdate,
    user: User = Depends(require_permission("ledgers", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} updating cost category {category_id} for company {user.company_id}")
    result = await db.execute(
        select(MstCostCategory)
        .where(MstCostCategory.category_id == category_id, MstCostCategory.company_id == user.company_id)
    )
    cc = result.scalars().first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost Category not found.")

    # Check for name conflict
    if payload.name != cc.name:
        conflict_res = await db.execute(
            select(MstCostCategory)
            .where(MstCostCategory.company_id == user.company_id, MstCostCategory.name == payload.name)
        )
        if conflict_res.scalars().first():
            raise HTTPException(status_code=400, detail="Another Cost Category with this name already exists.")

    cc.name = payload.name
    cc.alias = payload.alias
    cc.allocate_revenue = payload.allocate_revenue
    cc.allocate_non_revenue = payload.allocate_non_revenue
    cc.is_active = payload.is_active

    await db.flush()
    
    new_sq = SyncQueue(company_id=cc.company_id, record_type="CostCategory", record_id=cc.category_id, action="Alter", is_processed=False)
    db.add(new_sq)
    await db.commit()
    await db.refresh(cc)

    await try_push_cost_category_realtime(cc.category_id, new_sq.sync_id, "Alter", db)

    return cc

@router.delete("/cost-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost_category(
    category_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} deleting cost category {category_id} for company {user.company_id}")
    result = await db.execute(
        select(MstCostCategory)
        .where(MstCostCategory.category_id == category_id, MstCostCategory.company_id == user.company_id)
    )
    cc = result.scalars().first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost Category not found.")

    # In a full ERP, check if cost category is used in TrnCostCategoryCentre before deletion.

    new_sq = SyncQueue(company_id=cc.company_id, record_type="CostCategory", record_id=cc.category_id, action="Delete", is_processed=False)
    db.add(new_sq)
    await db.flush()

    # Trigger Tally Sync
    await try_push_cost_category_realtime(cc.category_id, new_sq.sync_id, "Delete", db)

    await db.delete(cc)
    await db.commit()
    return status.HTTP_204_NO_CONTENT

# ==========================
# Cost Centres Endpoints
# ==========================

@router.get("/cost-centres", response_model=List[CostCentreResponse])
async def list_cost_centres(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} fetching list of cost centres for company {user.company_id}")
    result = await db.execute(
        select(MstCostCentre, MstCostCategory.name.label("category_name"))
        .outerjoin(MstCostCategory, MstCostCentre.category_id == MstCostCategory.category_id)
        .where(MstCostCentre.company_id == user.company_id)
        .order_by(MstCostCentre.name.asc())
    )
    rows = result.all()
    
    response = []
    for row in rows:
        cc, cat_name = row
        cc_dict = {
            "cost_centre_id": cc.cost_centre_id,
            "company_id": cc.company_id,
            "name": cc.name,
            "alias": cc.alias,
            "category_id": cc.category_id,
            "parent_id": cc.parent_id,
            "is_active": cc.is_active,
            "category_name": cat_name
        }
        response.append(CostCentreResponse(**cc_dict))
    return response

@router.get("/cost-centres/tree", response_model=List[CostCentreTreeNode])
async def get_cost_centres_tree(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} fetching cost centres tree for company {user.company_id}")
    result = await db.execute(
        select(MstCostCentre, MstCostCategory.name.label("category_name"))
        .outerjoin(MstCostCategory, MstCostCentre.category_id == MstCostCategory.category_id)
        .where(MstCostCentre.company_id == user.company_id)
        .order_by(MstCostCentre.name.asc())
    )
    rows = result.all()

    node_map = {}
    for row in rows:
        cc, cat_name = row
        node_map[cc.cost_centre_id] = CostCentreTreeNode(
            cost_centre_id=cc.cost_centre_id,
            company_id=cc.company_id,
            name=cc.name,
            alias=cc.alias,
            category_id=cc.category_id,
            parent_id=cc.parent_id,
            is_active=cc.is_active,
            category_name=cat_name,
            children=[]
        )

    tree = []
    for node_id, node in node_map.items():
        if node.parent_id and node.parent_id in node_map:
            node_map[node.parent_id].children.append(node)
        else:
            tree.append(node)

    return tree

@router.post("/cost-centres", response_model=CostCentreResponse, status_code=status.HTTP_201_CREATED)
async def create_cost_centre(
    payload: CostCentreCreate,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} creating cost centre: {payload.name} for company {user.company_id}")
    # Check if category exists
    cat = (await db.execute(select(MstCostCategory).where(MstCostCategory.category_id == payload.category_id, MstCostCategory.company_id == user.company_id))).scalars().first()
    if not cat:
        logger.warning(f"User {user.user_id} tried to create cost centre with invalid category_id {payload.category_id}")
        raise HTTPException(status_code=400, detail="Cost Category not found")

    new_cc = MstCostCentre(
        company_id=user.company_id,
        name=payload.name,
        alias=payload.alias,
        category_id=payload.category_id,
        parent_id=payload.parent_id,
        is_active=payload.is_active
    )
    db.add(new_cc)
    await db.flush()
    
    new_sq = SyncQueue(company_id=new_cc.company_id, record_type="CostCentre", record_id=new_cc.cost_centre_id, action="Create", is_processed=False)
    db.add(new_sq)
    await db.commit()
    await db.refresh(new_cc)
    
    await try_push_cost_centre_realtime(new_cc.cost_centre_id, new_sq.sync_id, "Create", db)

    return CostCentreResponse(
        cost_centre_id=new_cc.cost_centre_id,
        company_id=new_cc.company_id,
        name=new_cc.name,
        alias=new_cc.alias,
        category_id=new_cc.category_id,
        parent_id=new_cc.parent_id,
        is_active=new_cc.is_active,
        category_name=cat.name
    )

@router.put("/cost-centres/{cost_centre_id}", response_model=CostCentreResponse)
async def update_cost_centre(
    cost_centre_id: int,
    payload: CostCentreUpdate,
    user: User = Depends(require_permission("ledgers", "update")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} updating cost centre {cost_centre_id} for company {user.company_id}")
    cc = (await db.execute(select(MstCostCentre).where(MstCostCentre.cost_centre_id == cost_centre_id, MstCostCentre.company_id == user.company_id))).scalars().first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost Centre not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(cc, key, value)

    new_sq = SyncQueue(company_id=cc.company_id, record_type="CostCentre", record_id=cc.cost_centre_id, action="Alter", is_processed=False)
    db.add(new_sq)

    await db.commit()
    await db.refresh(cc)
    
    await try_push_cost_centre_realtime(cc.cost_centre_id, new_sq.sync_id, "Alter", db)
    
    cat = (await db.execute(select(MstCostCategory).where(MstCostCategory.category_id == cc.category_id))).scalars().first()

    return CostCentreResponse(
        cost_centre_id=cc.cost_centre_id,
        company_id=cc.company_id,
        name=cc.name,
        alias=cc.alias,
        category_id=cc.category_id,
        parent_id=cc.parent_id,
        is_active=cc.is_active,
        category_name=cat.name if cat else None
    )

@router.delete("/cost-centres/{cost_centre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost_centre(
    cost_centre_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"User {user.user_id} deleting cost centre {cost_centre_id} for company {user.company_id}")
    cc = (await db.execute(select(MstCostCentre).where(MstCostCentre.cost_centre_id == cost_centre_id, MstCostCentre.company_id == user.company_id))).scalars().first()
    if not cc:
        raise HTTPException(status_code=404, detail="Cost Centre not found")

    new_sq = SyncQueue(company_id=cc.company_id, record_type="CostCentre", record_id=cc.cost_centre_id, action="Delete", is_processed=False)
    db.add(new_sq)
    await db.flush()

    await try_push_cost_centre_realtime(cc.cost_centre_id, new_sq.sync_id, "Delete", db)

    await db.delete(cc)
    await db.commit()
    return status.HTTP_204_NO_CONTENT

# ==========================================
# Cost Centre Classes
# ==========================================
async def get_cost_centre_class_by_id(class_id: int, company_id: int, db: AsyncSession):
    from sqlalchemy.orm import selectinload
    stmt = select(MstCostCentreClass).options(
        selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.category),
        selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.cost_centre)
    ).where(MstCostCentreClass.class_id == class_id, MstCostCentreClass.company_id == company_id)
    cls = (await db.execute(stmt)).scalars().first()
    if not cls: return None
    
    cls_dict = {
        "class_id": cls.class_id,
        "company_id": cls.company_id,
        "name": cls.name,
        "allocations": []
    }
    for alloc in cls.allocations:
        cls_dict["allocations"].append({
            "allocation_id": alloc.allocation_id,
            "class_id": alloc.class_id,
            "category_id": alloc.category_id,
            "cost_centre_id": alloc.cost_centre_id,
            "percentage": alloc.percentage,
            "category_name": alloc.category.name if alloc.category else None,
            "cost_centre_name": alloc.cost_centre.name if alloc.cost_centre else None
        })
    return cls_dict

@router.get("/cost-centre-classes", response_model=List[CostCentreClassResponse])
async def list_cost_centre_classes(
    user: User = Depends(require_permission("ledgers", "read")),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy.orm import selectinload
    stmt = select(MstCostCentreClass).options(
        selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.category),
        selectinload(MstCostCentreClass.allocations).selectinload(MstCostCentreClassAllocation.cost_centre)
    ).where(MstCostCentreClass.company_id == user.company_id)
    res = await db.execute(stmt)
    classes = res.scalars().all()
    
    result = []
    for cls in classes:
        cls_dict = {
            "class_id": cls.class_id,
            "company_id": cls.company_id,
            "name": cls.name,
            "allocations": []
        }
        for alloc in cls.allocations:
            cls_dict["allocations"].append({
                "allocation_id": alloc.allocation_id,
                "class_id": alloc.class_id,
                "category_id": alloc.category_id,
                "cost_centre_id": alloc.cost_centre_id,
                "percentage": alloc.percentage,
                "category_name": alloc.category.name if alloc.category else None,
                "cost_centre_name": alloc.cost_centre.name if alloc.cost_centre else None
            })
        result.append(cls_dict)
    
    return result

@router.post("/cost-centre-classes", response_model=CostCentreClassResponse, status_code=status.HTTP_201_CREATED)
async def create_cost_centre_class(
    payload: CostCentreClassCreate,
    user: User = Depends(require_permission("ledgers", "create")),
    db: AsyncSession = Depends(get_db)
):
    from app.routers.sync import try_push_cost_centre_class_realtime
    # Validate sum is <= 100 per category
    category_sums = {}
    for alloc in payload.allocations:
        category_sums[alloc.category_id] = category_sums.get(alloc.category_id, 0) + alloc.percentage
        if category_sums[alloc.category_id] > 100:
            raise HTTPException(status_code=400, detail=f"Total percentage for a category cannot exceed 100%.")

    new_cls = MstCostCentreClass(
        company_id=user.company_id,
        name=payload.name
    )
    db.add(new_cls)
    await db.flush()
    
    for alloc in payload.allocations:
        new_alloc = MstCostCentreClassAllocation(
            class_id=new_cls.class_id,
            category_id=alloc.category_id,
            cost_centre_id=alloc.cost_centre_id,
            percentage=alloc.percentage
        )
        db.add(new_alloc)
        
    await db.flush()
    
    new_sq = SyncQueue(company_id=new_cls.company_id, record_type="CostCentreClass", record_id=new_cls.class_id, action="Create", is_processed=False)
    db.add(new_sq)
    await db.commit()
    
    await try_push_cost_centre_class_realtime(new_cls.class_id, new_sq.sync_id, "Create", db)
    return await get_cost_centre_class_by_id(new_cls.class_id, user.company_id, db)

@router.put("/cost-centre-classes/{class_id}", response_model=CostCentreClassResponse)
async def update_cost_centre_class(
    class_id: int,
    payload: CostCentreClassUpdate,
    user: User = Depends(require_permission("ledgers", "update")),
    db: AsyncSession = Depends(get_db)
):
    from app.routers.sync import try_push_cost_centre_class_realtime
    from sqlalchemy import delete
    cls = (await db.execute(select(MstCostCentreClass).where(MstCostCentreClass.class_id == class_id, MstCostCentreClass.company_id == user.company_id))).scalars().first()
    if not cls:
        raise HTTPException(status_code=404, detail="Cost Centre Class not found")
        
    if payload.name is not None:
        cls.name = payload.name
        
    if payload.allocations is not None:
        category_sums = {}
        for alloc in payload.allocations:
            category_sums[alloc.category_id] = category_sums.get(alloc.category_id, 0) + alloc.percentage
            if category_sums[alloc.category_id] > 100:
                raise HTTPException(status_code=400, detail=f"Total percentage for a category cannot exceed 100%.")

        await db.execute(delete(MstCostCentreClassAllocation).where(MstCostCentreClassAllocation.class_id == class_id))
        
        for alloc in payload.allocations:
            new_alloc = MstCostCentreClassAllocation(
                class_id=class_id,
                category_id=alloc.category_id,
                cost_centre_id=alloc.cost_centre_id,
                percentage=alloc.percentage
            )
            db.add(new_alloc)
            
    await db.flush()
    new_sq = SyncQueue(company_id=cls.company_id, record_type="CostCentreClass", record_id=cls.class_id, action="Alter", is_processed=False)
    db.add(new_sq)
    await db.commit()
    
    await try_push_cost_centre_class_realtime(cls.class_id, new_sq.sync_id, "Alter", db)
    return await get_cost_centre_class_by_id(cls.class_id, user.company_id, db)

@router.delete("/cost-centre-classes/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost_centre_class(
    class_id: int,
    user: User = Depends(require_permission("ledgers", "delete")),
    db: AsyncSession = Depends(get_db)
):
    from app.routers.sync import try_push_cost_centre_class_realtime
    cls = (await db.execute(select(MstCostCentreClass).where(MstCostCentreClass.class_id == class_id, MstCostCentreClass.company_id == user.company_id))).scalars().first()
    if not cls:
        raise HTTPException(status_code=404, detail="Cost Centre Class not found")

    new_sq = SyncQueue(company_id=cls.company_id, record_type="CostCentreClass", record_id=cls.class_id, action="Delete", is_processed=False)
    db.add(new_sq)
    await db.flush()

    await try_push_cost_centre_class_realtime(cls.class_id, new_sq.sync_id, "Delete", db)
    await db.delete(cls)
    await db.commit()
    return status.HTTP_204_NO_CONTENT
