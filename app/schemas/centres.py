import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CentreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=500)


class CentreOut(BaseModel):
    id: uuid.UUID
    name: str
    location: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TestCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(gt=0, decimal_places=2)


class TestOut(BaseModel):
    id: uuid.UUID
    name: str
    price: Decimal
    centre_id: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedCentres(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[CentreOut]


class PaginatedTests(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TestOut]
