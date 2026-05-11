"""환경설정 및 경로. 우선순위: 환경변수 → 기본값."""

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = Path(os.environ.get('DB_PATH', str(DATA_DIR / 'trading.db')))

# 브로커 선택: 'mock' (yfinance 가상매매) | 'kis' (한국투자증권)
BROKER = os.environ.get('BROKER', 'mock')

# KIS API (Phase 2에서 사용)
KIS_APP_KEY = os.environ.get('KIS_APP_KEY', '')
KIS_APP_SECRET = os.environ.get('KIS_APP_SECRET', '')
KIS_ACCOUNT_NO = os.environ.get('KIS_ACCOUNT_NO', '')
KIS_IS_PAPER = os.environ.get('KIS_IS_PAPER', 'true').lower() == 'true'

# 엔진 사이클 주기
ENGINE_INTERVAL_SECONDS = int(os.environ.get('ENGINE_INTERVAL_SECONDS', '60'))

# 안전장치 (Phase 3)
# 일일 손실 한도. baseline 자산 대비 -N% 도달 시 kill switch 자동 트립. 0이면 비활성.
DAILY_LOSS_LIMIT_PCT = float(os.environ.get('DAILY_LOSS_LIMIT_PCT', '5.0'))
# 같은 종목 × 같은 action(BUY/SELL) 중복 주문을 차단하는 시간 윈도우(초). 0이면 비활성.
ORDER_IDEMPOTENCY_WINDOW_SEC = int(os.environ.get('ORDER_IDEMPOTENCY_WINDOW_SEC', '60'))
# True면 시장 시간(KR 09:00-15:30 KST / US 09:30-16:00 ET)에만 주문 허용.
# 평일/주말만 판단하며 한국·미국 휴장일은 Phase 5에서 캘린더 도입 예정.
MARKET_HOURS_STRICT = os.environ.get('MARKET_HOURS_STRICT', 'false').lower() == 'true'

# 대시보드 표시 보조값 (Phase 4에서 portfolio 테이블로 이전 예정)
TOTAL_CAPITAL = float(os.environ.get('TOTAL_CAPITAL', '3400.0'))
DASHBOARD_REFRESH_SEC = int(os.environ.get('DASHBOARD_REFRESH_SEC', '1'))
PRICE_REFRESH_SEC = int(os.environ.get('PRICE_REFRESH_SEC', '60'))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
