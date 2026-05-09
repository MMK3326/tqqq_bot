"""
한국투자증권(KIS) API 연동용 broker 계층.

현재 프로젝트는 모의투자 흐름 검증 단계이므로 실제 API 호출은 구현하지 않는다.
나중에 이 파일 안에서만 인증, 현재가 조회, 잔고 조회, 주문 API를 연결하면
strategy와 main 코드는 그대로 유지할 수 있다.
"""


def get_current_price(symbol: str) -> float:
    # TODO: 한국투자증권 해외주식 현재가 조회 API 연결
    raise NotImplementedError("KIS 현재가 조회 API는 아직 구현되지 않았습니다.")


def get_cash_balance() -> float:
    # TODO: 한국투자증권 주문 가능 현금 조회 API 연결
    raise NotImplementedError("KIS 현금 잔고 조회 API는 아직 구현되지 않았습니다.")


def get_position(symbol: str) -> dict:
    # TODO: 한국투자증권 해외주식 잔고 조회 API 연결
    raise NotImplementedError("KIS 보유 포지션 조회 API는 아직 구현되지 않았습니다.")


def buy_market(symbol: str, amount: float) -> dict:
    # TODO: amount를 주문 가능 수량으로 변환한 뒤 해외주식 매수 API 연결
    raise NotImplementedError("KIS 매수 주문 API는 아직 구현되지 않았습니다.")


def sell_market(symbol: str, quantity: float) -> dict:
    # TODO: 해외주식 매도 API 연결
    raise NotImplementedError("KIS 매도 주문 API는 아직 구현되지 않았습니다.")
