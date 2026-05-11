"""한국투자증권 KIS Developers API 브로커 스켈레톤.

Phase 2에서 토큰/시세/주문/잔고를 실제 구현한다. 현재는 인터페이스 형태만 잡아둔다.
국내(KR)/해외(US) 분기와 모의(KIS_IS_PAPER=true)/실전 분기를 내부에서 처리할 예정.
"""

from typing import Any, Optional

from .. import config
from .base import Broker, MarketData, OrderFill


class KISBroker(Broker):
    name = 'kis'

    def __init__(self,
                 app_key: str | None = None,
                 app_secret: str | None = None,
                 account_no: str | None = None,
                 is_paper: bool | None = None) -> None:
        self.app_key = app_key or config.KIS_APP_KEY
        self.app_secret = app_secret or config.KIS_APP_SECRET
        self.account_no = account_no or config.KIS_ACCOUNT_NO
        self.is_paper = config.KIS_IS_PAPER if is_paper is None else bool(is_paper)
        self._access_token: str | None = None

    # ---- Phase 2에서 구현 ----------------------------------------------------

    def get_market_data(self, ticker: str, market: str, lookback: int = 100) -> MarketData:
        raise NotImplementedError('KIS 시세 조회는 Phase 2에서 구현됩니다.')

    def get_current_price(self, ticker: str, market: str) -> float:
        raise NotImplementedError('KIS 현재가 조회는 Phase 2에서 구현됩니다.')

    def place_order(self, ticker: str, market: str, side: str, quantity: float,
                    price: Optional[float] = None) -> OrderFill:
        raise NotImplementedError('KIS 주문은 Phase 2에서 구현됩니다.')

    def get_positions(self) -> list[dict[str, Any]]:
        raise NotImplementedError('KIS 잔고 조회는 Phase 2에서 구현됩니다.')

    def get_balance(self) -> dict[str, Any]:
        raise NotImplementedError('KIS 현금 조회는 Phase 2에서 구현됩니다.')
