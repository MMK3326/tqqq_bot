"""주문 이력, 시그널 로그, 자산 추이 API (Phase 4)."""

from typing import Optional

from fastapi import APIRouter

from .. import db

router = APIRouter(tags=['history'])


@router.get('/api/orders')
def list_orders(limit: int = 100, position_id: Optional[int] = None):
    return db.list_orders(position_id=position_id, limit=limit)


@router.get('/api/signals')
def list_signals(limit: int = 100, position_id: Optional[int] = None):
    return db.list_signals(position_id=position_id, limit=limit)


@router.get('/api/equity')
def list_equity(limit: int = 200):
    rows = db.list_equity_snapshots(limit=limit)
    rows.reverse()  # 오래된 → 최신 순
    return rows
