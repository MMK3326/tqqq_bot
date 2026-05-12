"""종목(positions) CRUD API."""

from fastapi import APIRouter, HTTPException

from .. import db
from ..models import PositionCreate, PositionOut, PositionUpdate
from ..strategies import REGISTRY


router = APIRouter(prefix='/api/positions', tags=['positions'])


def _check_strategy(name: str) -> None:
    if name not in REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"등록되지 않은 전략: '{name}'. 사용 가능: {list(REGISTRY)}",
        )


@router.get('', response_model=list[PositionOut])
def list_positions():
    return db.list_positions()


@router.post('', response_model=PositionOut, status_code=201)
def create_position(payload: PositionCreate):
    _check_strategy(payload.strategy)
    pos_id = db.insert_position(
        ticker=payload.ticker,
        market=payload.market,
        name=payload.name,
        strategy=payload.strategy,
        params=payload.params,
        budget=payload.budget,
        enabled=payload.enabled,
    )
    return db.get_position(pos_id)


@router.patch('/{position_id}', response_model=PositionOut)
def update_position(position_id: int, payload: PositionUpdate):
    if not db.get_position(position_id):
        raise HTTPException(status_code=404, detail='종목을 찾을 수 없습니다.')
    fields = payload.model_dump(exclude_unset=True)
    if 'strategy' in fields:
        _check_strategy(fields['strategy'])
    if fields:
        db.update_position(position_id, fields=fields)
    return db.get_position(position_id)


@router.delete('/{position_id}', status_code=204)
def delete_position(position_id: int):
    if not db.get_position(position_id):
        raise HTTPException(status_code=404, detail='종목을 찾을 수 없습니다.')
    db.delete_position(position_id)
