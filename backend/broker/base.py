"""브로커 추상 인터페이스 + 공용 데이터 클래스."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MarketData:
    """전략이 받는 시장 데이터 컨테이너.

    Phase 1에서는 last_price만 채우고, RSI/MA 등 시계열이 필요한 전략은
    Phase 2에서 history와 헬퍼 메서드를 추가한다.
    """
    ticker: str
    market: str
    last_price: float
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OrderFill:
    """브로커가 체결을 보고할 때 사용하는 단순 구조체."""
    ticker: str
    market: str
    action: str           # 'BUY' | 'SELL'
    price: float
    quantity: float
    amount: float
    ts: str


class Broker(ABC):
    @abstractmethod
    def get_market_data(self, ticker: str, market: str, lookback: int = 100) -> MarketData:
        ...

    @abstractmethod
    def get_current_price(self, ticker: str, market: str) -> float:
        ...

    @abstractmethod
    def place_order(self, ticker: str, market: str, side: str, quantity: float,
                    price: Optional[float] = None) -> OrderFill:
        ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_balance(self) -> dict[str, Any]:
        ...
