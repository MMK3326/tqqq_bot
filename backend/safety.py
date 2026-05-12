"""안전장치 모음 (Phase 3).

- 전역 kill switch (수동 트립 + 일일 손실 한도 자동 트립)
- 장 시간 차단 (KR / US 정규장)
- 주문 멱등성 (같은 종목 × 같은 action 짧은 시간 중복 차단)
- 포트폴리오 평가 + 일일 baseline 관리

엔진과 control 라우터가 이 모듈을 사용한다. 결과는 SafetyDecision으로 통일한다.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import config, db


KILL_SWITCH_ACTIVE = 'kill_switch_active'
KILL_SWITCH_REASON = 'kill_switch_reason'
KILL_SWITCH_TRIPPED_AT = 'kill_switch_tripped_at'
DAILY_BASELINE_DATE = 'daily_baseline_date'
DAILY_BASELINE_ASSET = 'daily_baseline_asset'


@dataclass
class SafetyDecision:
    allowed: bool
    reason: str = ''

    @classmethod
    def ok(cls) -> 'SafetyDecision':
        return cls(allowed=True)

    @classmethod
    def block(cls, reason: str) -> 'SafetyDecision':
        return cls(allowed=False, reason=reason)


# ---- Kill switch ------------------------------------------------------------

def is_kill_switch_active() -> bool:
    return db.get_system_state(KILL_SWITCH_ACTIVE) == '1'


def kill_switch_status() -> dict[str, Any]:
    return {
        'active': is_kill_switch_active(),
        'reason': db.get_system_state(KILL_SWITCH_REASON) or '',
        'trippedAt': db.get_system_state(KILL_SWITCH_TRIPPED_AT) or '',
    }


def trip_kill_switch(reason: str) -> None:
    db.set_system_state(KILL_SWITCH_ACTIVE, '1')
    db.set_system_state(KILL_SWITCH_REASON, reason)
    db.set_system_state(KILL_SWITCH_TRIPPED_AT, datetime.now().isoformat(timespec='seconds'))


def reset_kill_switch() -> None:
    db.set_system_state(KILL_SWITCH_ACTIVE, '0')
    db.set_system_state(KILL_SWITCH_REASON, '')
    db.set_system_state(KILL_SWITCH_TRIPPED_AT, '')


# ---- Market hours -----------------------------------------------------------

def _zone(name: str) -> ZoneInfo | None:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None


_KR = _zone('Asia/Seoul')
_US = _zone('America/New_York')


def is_market_open(market: str, now: datetime | None = None) -> bool:
    """정규장 시간 기준. 휴장일(공휴일) 캘린더는 Phase 5에서 추가."""
    now = now or datetime.now().astimezone()
    if market == 'KR' and _KR:
        local = now.astimezone(_KR)
        if local.weekday() >= 5:
            return False
        return time(9, 0) <= local.time() <= time(15, 30)
    if market == 'US' and _US:
        local = now.astimezone(_US)
        if local.weekday() >= 5:
            return False
        return time(9, 30) <= local.time() <= time(16, 0)
    return True


def check_market_hours(market: str) -> SafetyDecision:
    if not config.MARKET_HOURS_STRICT:
        return SafetyDecision.ok()
    if is_market_open(market):
        return SafetyDecision.ok()
    return SafetyDecision.block(f'장외 시간 ({market}) — MARKET_HOURS_STRICT=true')


# ---- Order idempotency ------------------------------------------------------

def check_idempotency(position_id: int, action: str) -> SafetyDecision:
    window = int(config.ORDER_IDEMPOTENCY_WINDOW_SEC)
    if window <= 0:
        return SafetyDecision.ok()
    last = db.get_last_order(position_id)
    if not last or last.get('action') != action:
        return SafetyDecision.ok()
    try:
        last_ts = datetime.fromisoformat(last['ts'])
    except (TypeError, ValueError):
        return SafetyDecision.ok()
    age = (datetime.now() - last_ts).total_seconds()
    if age < window:
        return SafetyDecision.block(
            f'멱등성 차단: 직전 {action}로부터 {int(age)}초만 경과 (윈도우 {window}초)'
        )
    return SafetyDecision.ok()


# ---- Portfolio value + daily loss limit ------------------------------------

def portfolio_value(broker, positions: list[dict[str, Any]]) -> dict[str, float]:
    """단순 포트폴리오 평가.

    - market_value: 보유 수량 × 현재가 (시세 조회 실패 시 평단가로 폴백)
    - invested: 누적 투입 금액 합
    - cash_equivalent: 아직 쓰지 않은 예산 (budget_sum - invested)
    - total: market_value + cash_equivalent
    """
    market_value = 0.0
    invested = 0.0
    budget_sum = 0.0
    for p in positions:
        st = p.get('state') or {}
        pos_invested = float(st.get('invested_amount', 0.0))
        qty = float(st.get('quantity', 0.0))
        invested += pos_invested
        budget_sum += float(p.get('budget', 0.0))
        if qty > 0:
            try:
                price = broker.get_current_price(p['ticker'], p['market'])
            except Exception:
                price = float(st.get('avg_price', 0.0))
            market_value += qty * price
    cash_equivalent = max(0.0, budget_sum - invested)
    return {
        'total': market_value + cash_equivalent,
        'market_value': market_value,
        'invested': invested,
        'cash_equivalent': cash_equivalent,
        'budget_sum': budget_sum,
    }


def check_daily_loss_limit(broker, positions: list[dict[str, Any]]) -> SafetyDecision:
    """오늘 baseline 자산 대비 손실이 DAILY_LOSS_LIMIT_PCT 이상이면 kill switch 트립."""
    limit_pct = float(config.DAILY_LOSS_LIMIT_PCT)
    if limit_pct <= 0:
        return SafetyDecision.ok()

    today = date.today().isoformat()
    baseline_date = db.get_system_state(DAILY_BASELINE_DATE)
    snapshot = portfolio_value(broker, positions)
    current = snapshot['total']

    if baseline_date != today:
        db.set_system_state(DAILY_BASELINE_DATE, today)
        db.set_system_state(DAILY_BASELINE_ASSET, str(current))
        return SafetyDecision.ok()

    try:
        baseline = float(db.get_system_state(DAILY_BASELINE_ASSET) or 0.0)
    except ValueError:
        baseline = 0.0
    if baseline <= 0:
        db.set_system_state(DAILY_BASELINE_ASSET, str(current))
        return SafetyDecision.ok()

    drop_pct = (baseline - current) / baseline * 100
    if drop_pct >= limit_pct:
        reason = (
            f'일일 손실 한도 도달: baseline ${baseline:,.2f} → 현재 ${current:,.2f} '
            f'(-{drop_pct:.2f}%, 한도 {limit_pct:.2f}%)'
        )
        trip_kill_switch(reason)
        return SafetyDecision.block(reason)
    return SafetyDecision.ok()
