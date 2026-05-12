from .. import config
from .base import Broker, MarketData, OrderFill
from .kis import KISBroker
from .mock import MockBroker


def get_broker() -> Broker:
    """config.BROKER 값에 따라 브로커 인스턴스를 반환한다."""
    if config.BROKER == 'mock':
        return MockBroker()
    if config.BROKER == 'kis':
        return KISBroker()
    raise ValueError(f"알 수 없는 브로커: '{config.BROKER}'. 'mock' 또는 'kis' 사용")


__all__ = ['Broker', 'MarketData', 'OrderFill', 'MockBroker', 'KISBroker', 'get_broker']
