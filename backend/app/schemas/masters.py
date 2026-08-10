from pydantic import BaseModel
from typing import Optional, List

# ==========================
# Cost Category Schemas
# ==========================
class CostCategoryBase(BaseModel):
    name: str
    alias: Optional[str] = None
    allocate_revenue: bool = True
    allocate_non_revenue: bool = False
    is_active: bool = True

class CostCategoryCreate(CostCategoryBase):
    pass

class CostCategoryUpdate(CostCategoryBase):
    pass

class CostCategoryResponse(CostCategoryBase):
    category_id: int
    company_id: int

    class Config:
        from_attributes = True

# ==========================
# Cost Centre Schemas
# ==========================
class CostCentreBase(BaseModel):
    name: str
    alias: Optional[str] = None
    category_id: int
    parent_id: Optional[int] = None
    is_active: bool = True

class CostCentreCreate(CostCentreBase):
    pass

class CostCentreUpdate(BaseModel):
    name: Optional[str] = None
    alias: Optional[str] = None
    category_id: Optional[int] = None
    parent_id: Optional[int] = None
    is_active: Optional[bool] = None

class CostCentreResponse(CostCentreBase):
    cost_centre_id: int
    company_id: int
    category_name: Optional[str] = None

    class Config:
        from_attributes = True

class CostCentreTreeNode(CostCentreResponse):
    children: List['CostCentreTreeNode'] = []

# ==========================
# Cost Centre Class Schemas
# ==========================
class CostCentreClassAllocationBase(BaseModel):
    category_id: int
    cost_centre_id: int
    percentage: float

class CostCentreClassAllocationResponse(CostCentreClassAllocationBase):
    allocation_id: int
    class_id: int
    category_name: Optional[str] = None
    cost_centre_name: Optional[str] = None
    
    class Config:
        from_attributes = True

class CostCentreClassBase(BaseModel):
    name: str

class CostCentreClassCreate(CostCentreClassBase):
    allocations: List[CostCentreClassAllocationBase]

class CostCentreClassUpdate(BaseModel):
    name: Optional[str] = None
    allocations: Optional[List[CostCentreClassAllocationBase]] = None

class CostCentreClassResponse(CostCentreClassBase):
    class_id: int
    company_id: int
    allocations: List[CostCentreClassAllocationResponse] = []

    class Config:
        from_attributes = True
