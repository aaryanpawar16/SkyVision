from pydantic import BaseModel
from typing import Any, Dict, Optional


class Hit(BaseModel):
    id: int
    name: str
    city: Optional[str] = None
    country: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    distance: float


class RankedResult(BaseModel):
    count: int
    hits: list[Hit]
