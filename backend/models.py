"""API 입출력용 Pydantic 모델."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class PositionCreate(BaseModel):
    ticker: str
    market: str = Field(pattern='^(KR|US)$')
    name: Optional[str] = None
    strategy: str
    params: dict[str, Any] = {}
    budget: float = 0
    enabled: bool = True


class PositionUpdate(BaseModel):
    ticker: Optional[str] = None
    market: Optional[str] = Field(default=None, pattern='^(KR|US)$')
    name: Optional[str] = None
    strategy: Optional[str] = None
    params: Optional[dict[str, Any]] = None
    budget: Optional[float] = None
    enabled: Optional[bool] = None


class PositionOut(BaseModel):
    id: int
    ticker: str
    market: str
    name: Optional[str]
    strategy: str
    params: dict[str, Any]
    budget: float
    enabled: bool
    state: dict[str, Any]
    created_at: str
    updated_at: str


class StrategyOut(BaseModel):
    name: str
    display_name: str
    supported_markets: list[str]
    params_schema: dict[str, Any]
