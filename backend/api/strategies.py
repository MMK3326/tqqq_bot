"""전략 목록 API. 대시보드 종목 추가 폼이 이 응답으로 동적 필드를 그린다."""

from fastapi import APIRouter

from ..models import StrategyOut
from ..strategies import list_strategies


router = APIRouter(prefix='/api/strategies', tags=['strategies'])


@router.get('', response_model=list[StrategyOut])
def get_strategies():
    return list_strategies()
