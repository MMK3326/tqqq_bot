"""
TQQQ 1단계 전략 테스트용 설정 파일.

이 프로젝트는 실전 수익 최적화가 아니라 매수, 추가매수, 익절,
평단 계산, 로그 기록, 상태 저장 흐름을 빠르게 검증하는 목적이다.
"""

# "mock": 모의투자, "real": 한국투자증권 API 연동 자리
MODE = "mock"

# 거래 대상 종목
SYMBOL = "TQQQ"

# 전체 기준 자산
TOTAL_CAPITAL = 3400.0

# 현금으로 남겨둘 비율
CASH_RESERVE_RATIO = 0.30

# 실제 전략 운용 비율. TOTAL_CAPITAL * 0.70 = 2380달러
MAX_INVEST_RATIO = 0.70

# 운용 가능 금액을 몇 분할로 나눌지 설정
BASE_SPLIT_COUNT = 40

# 최초 기준가 대비 추가매수 간격
DROP_INTERVAL_PCT = 0.5

# 전체 평단가 대비 익절 기준
TAKE_PROFIT_PCT = 0.5

# yfinance 현재가 갱신 주기
PRICE_REFRESH_SEC = 60
STRATEGY_RUN_INTERVAL_SEC = 60
DASHBOARD_REFRESH_SEC = 1

# True: 현재가 기준 정수 주 단위로 1분할 금액 보정
# False: 소수점 수량 매수 허용
USE_INTEGER_SHARE_UNIT = True
