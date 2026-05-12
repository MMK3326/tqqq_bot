"""모의 브로커: yfinance로 시세 조회, 주문은 즉시 체결되는 것으로 가상 처리.

브로커는 무상태이며, 보유 수량/평단가 등 실행 상태는 엔진이 DB(positions.state)에 저장한다.
"""

from datetime import datetime
from typing import Any, Optional

import yfinance as yf

from .. import config
from .base import Broker, MarketData, OrderFill


_LAST_PRICE_CACHE: dict[str, float] = {}


def _init_yf_cache() -> None:
    cache_dir = config.BASE_DIR / '.yfinance_cache'
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        yf.set_tz_cache_location(str(cache_dir))
    except Exception:
        pass


_init_yf_cache()


def _yf_symbol(ticker: str, market: str) -> str:
    """KR 종목은 yfinance용 접미사(.KS/.KQ)를 붙인다. US는 그대로."""
    if market != 'KR':
        return ticker
    if ticker.endswith(('.KS', '.KQ')):
        return ticker
    # 코스닥/코스피 구분은 정확치 않으므로 사용자가 직접 .KQ를 명시하도록 권장.
    return f'{ticker}.KS'


class MockBroker(Broker):
    name = 'mock'

    def get_current_price(self, ticker: str, market: str) -> float:
        yf_sym = _yf_symbol(ticker, market)
        try:
            t = yf.Ticker(yf_sym)
            price = t.fast_info.get('last_price')
            if price is None:
                history = t.history(period='1d', interval='1m')
                if history.empty:
                    raise RuntimeError(f'{yf_sym} 시세 응답이 비어 있습니다.')
                price = history['Close'].dropna().iloc[-1]
            price = float(price)
            if price <= 0:
                raise RuntimeError(f'{yf_sym} 시세가 0 이하입니다.')
            _LAST_PRICE_CACHE[yf_sym] = price
            return price
        except Exception as exc:
            if yf_sym in _LAST_PRICE_CACHE:
                return _LAST_PRICE_CACHE[yf_sym]
            raise RuntimeError(f'{ticker}({market}) 현재가 조회 실패: {exc}') from exc

    def get_market_data(self, ticker: str, market: str, lookback: int = 100) -> MarketData:
        last_price = self.get_current_price(ticker, market)
        return MarketData(ticker=ticker, market=market, last_price=last_price)

    def place_order(self, ticker: str, market: str, side: str, quantity: float,
                    price: Optional[float] = None) -> OrderFill:
        if quantity <= 0:
            raise ValueError('주문 수량은 0보다 커야 합니다.')
        fill_price = float(price) if price is not None else self.get_current_price(ticker, market)
        return OrderFill(
            ticker=ticker,
            market=market,
            action=side.upper(),
            price=fill_price,
            quantity=float(quantity),
            amount=fill_price * float(quantity),
            ts=datetime.now().isoformat(timespec='seconds'),
        )

    def get_positions(self) -> list[dict[str, Any]]:
        # mock 브로커는 자체 포지션을 보관하지 않는다. 엔진이 DB로 관리.
        return []

    def get_balance(self) -> dict[str, Any]:
        return {'cash': None, 'note': 'mock 모드는 별도 잔고를 추적하지 않습니다.'}
