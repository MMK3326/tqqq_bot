"""Strategy 추상 클래스 + 공용 시그널/컨텍스트 구조.

파일 1개 = 전략 1개 원칙. 새 전략은 이 폴더 안에 .py 파일 하나만 추가하면 된다.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional


Action = Literal['BUY', 'SELL', 'HOLD']


@dataclass
class Signal:
    action: Action = 'HOLD'
    quantity: Optional[float] = None   # 명시 수량 (선택)
    amount: Optional[float] = None     # 명시 금액 (선택, BUY 시 quantity 대신)
    reason: str = ''
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyContext:
    """전략이 시장 데이터 외에 참고하는 실행 컨텍스트.

    - state: 현재 포지션 실행 상태
        (quantity, avg_price, first_price, invested_amount, bought_steps, cycle_count)
    - budget: 이 종목 할당 예산 (원/달러)
    - cash_balance: 현재 사용 가능한 현금 (mock에서는 budget - invested로 추정)
    """
    state: dict[str, Any]
    budget: float
    cash_balance: float


class Strategy(ABC):
    name: str = ''
    display_name: str = ''
    params_schema: dict[str, Any] = {}
    supported_markets: list[str] = ['KR', 'US']

    def __init__(self, params: dict[str, Any]):
        self.params = self._with_defaults(params)

    @classmethod
    def _with_defaults(cls, params: dict[str, Any]) -> dict[str, Any]:
        resolved: dict[str, Any] = {}
        for key, spec in cls.params_schema.items():
            if key in params:
                resolved[key] = params[key]
            elif isinstance(spec, dict) and 'default' in spec:
                resolved[key] = spec['default']
        # 스키마에 없지만 사용자가 넘긴 키도 보존
        for key, val in params.items():
            resolved.setdefault(key, val)
        return resolved

    @abstractmethod
    def generate_signal(self, market_data, context: StrategyContext) -> Signal:
        """현재 시장 데이터 + 포지션 컨텍스트로 매매 시그널을 만든다."""
        ...
