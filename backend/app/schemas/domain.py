from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

# Organization Schemas
class OrganizationBase(BaseModel):
    name: str
    document_number: Optional[str] = None

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationResponse(OrganizationBase):
    id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# EAP & Task Schemas
class EAPItemBase(BaseModel):
    code: str
    name: str
    item_type: str = "etapa" # etapa, subetapa, servico
    progress_percent: float = 0.0
    parent_id: Optional[str] = None

class EAPItemCreate(EAPItemBase):
    project_id: str

class EAPItemResponse(EAPItemBase):
    id: str
    project_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TaskItemBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "a_fazer" # a_fazer, em_andamento, concluido
    priority: str = "media" # alta, media, baixa
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    eap_item_id: Optional[str] = None

class TaskItemCreate(TaskItemBase):
    project_id: str

class TaskItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    due_date: Optional[str] = None
    eap_item_id: Optional[str] = None

class TaskItemResponse(TaskItemBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Daily Log Schemas
class DailyLogBase(BaseModel):
    date: str
    weather_condition: str = "ensolarado" # ensolarado, nublado, chuvoso, impraticavel
    manpower_own: int = 0
    manpower_subcontracted: int = 0
    activities_done: str
    occurrences: Optional[str] = None
    status: str = "assinado"

class DailyLogCreate(DailyLogBase):
    project_id: str

class DailyLogResponse(DailyLogBase):
    id: str
    project_id: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Project Schemas
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    city_ibge: str = "BR-RS-4311403"
    city_name: str = "Lajeado"
    state: str = "RS"
    zone: str = "Z2"
    building_type: str = "residencial_unifamiliar"
    lot_area: float = 0.0
    built_area: float = 0.0
    floors: int = 1
    front_setback: float = 0.0
    side_setback: float = 0.0
    rear_setback: float = 0.0
    occupancy_rate: float = 0.0
    permeability_rate: float = 20.0
    parking_spaces: int = 1

class ProjectCreate(ProjectBase):
    organization_id: str

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    zone: Optional[str] = None
    building_type: Optional[str] = None
    lot_area: Optional[float] = None
    built_area: Optional[float] = None
    floors: Optional[int] = None
    front_setback: Optional[float] = None
    side_setback: Optional[float] = None
    rear_setback: Optional[float] = None
    occupancy_rate: Optional[float] = None
    permeability_rate: Optional[float] = None
    parking_spaces: Optional[int] = None
    status: Optional[str] = None
    is_official_baseline: Optional[bool] = None

class ValidationRecordResponse(BaseModel):
    id: str
    rule_id: str
    rule_title: str
    status: str # conforme, nao_conforme, atencao, nao_verificavel
    field: str
    expected_value: str
    actual_value: str
    details: Optional[str] = None
    source_citation: Optional[str] = None
    validated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ProjectResponse(ProjectBase):
    id: str
    organization_id: str
    status: str
    is_official_baseline: bool
    created_at: datetime
    updated_at: datetime
    validations: List[ValidationRecordResponse] = []
    model_config = ConfigDict(from_attributes=True)

# Document Schemas
class DocumentCreate(BaseModel):
    project_id: str
    title: str
    category: str = "projeto_arquitetonico"
    version: str = "v1.0"

class DocumentResponse(BaseModel):
    id: str
    project_id: str
    title: str
    category: str
    version: str
    file_path: str
    hash_sha256: Optional[str] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Regulatory Engine Schemas
class RegulatoryAnalysisRequest(BaseModel):
    project_id: str

class RegulatoryAnalysisReport(BaseModel):
    project_id: str
    total_checks: int
    conforme_count: int
    nao_conforme_count: int
    atencao_count: int
    nao_verificavel_count: int
    results: List[ValidationRecordResponse]
