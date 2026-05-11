"""레거시 단일종목 대시보드 API.

기존 프론트엔드(`/api/dashboard`, `/api/control/*`)와의 호환을 유지하기 위한 어댑터.
DB(positions/orders/signals)에서 데이터를 읽어 기존 페이로드 모양 그대로 반환한다.

Phase 4에서 다중 종목 UI가 도입되면 이 라우터는 `/api/dashboard/summary` 등으로 분해된다.
"""

import threading
import time
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter

from .. import config, db, safety
from ..broker import Broker, get_broker
from ..engine import run_cycle


router = APIRouter(tags=['dashboard'])


# ---- 포맷 헬퍼 ---------------------------------------------------------------

def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def money(v: float) -> str:
    return f'${v:,.2f}'


def signed_money(v: float) -> str:
    sign = '+' if v >= 0 else '-'
    return f'{sign}${abs(v):,.2f}'


def pct(v: float, signed: bool = False) -> str:
    sign = '+' if signed and v >= 0 else ''
    return f'{sign}{v:.2f}%'


def qty(v: float) -> str:
    return f'{v:.6f}'


def compact_time(value: str) -> str:
    if not value:
        return '-'
    try:
        return datetime.fromisoformat(value).strftime('%H:%M:%S')
    except ValueError:
        return value[-8:] if len(value) >= 8 else value


def market_status_text() -> str:
    try:
        now = datetime.now(ZoneInfo('America/New_York'))
    except ZoneInfoNotFoundError:
        return '확인불가'
    if now.weekday() >= 5:
        return '장외'
    cur = now.time()
    pre = datetime.strptime('04:00', '%H:%M').time()
    reg = datetime.strptime('09:30', '%H:%M').time()
    close = datetime.strptime('16:00', '%H:%M').time()
    after = datetime.strptime('20:00', '%H:%M').time()
    if pre <= cur < reg:
        return '프리마켓'
    if reg <= cur < close:
        return '정규장'
    if close <= cur < after:
        return '애프터마켓'
    return '장외'


# ---- DB → 표시 계산 ----------------------------------------------------------

def _primary_position() -> dict[str, Any] | None:
    """단일종목 페이로드의 기준이 될 종목 1개 선택. enabled 우선, 그 다음 id 순."""
    positions = db.list_positions(enabled_only=False)
    if not positions:
        return None
    enabled = [p for p in positions if p['enabled']]
    return (enabled or positions)[0]


def _calc_metrics(state: dict[str, Any], price: float,
                  params: dict[str, Any], budget: float) -> dict[str, Any]:
    quantity = to_float(state.get('quantity'))
    avg_price = to_float(state.get('avg_price'))
    first_price = to_float(state.get('first_price'))
    invested = to_float(state.get('invested_amount'))
    bought_steps = [int(s) for s in (state.get('bought_steps') or [])]

    base_split_count = max(1, int(params.get('base_split_count', 40)))
    drop_interval_pct = float(params.get('drop_interval_pct', 0.5))
    take_profit_pct = float(params.get('take_profit_pct', 0.5))
    use_integer = bool(params.get('use_integer_share_unit', True))

    safe_price = price if price > 0 else max(avg_price, first_price, 1.0)
    raw_unit = budget / base_split_count
    if use_integer:
        shares = max(1, int(raw_unit // safe_price)) if safe_price > 0 else 1
        adjusted = shares * safe_price
    else:
        adjusted = raw_unit
        shares = (raw_unit / safe_price) if safe_price > 0 else 0.0

    remaining = max(0.0, budget - invested)
    profit_pct = ((price - avg_price) / avg_price * 100) if (quantity > 0 and avg_price > 0) else 0.0

    current_step = 0
    next_buy_price = 0.0
    if first_price > 0:
        drop_pct = max(0.0, (first_price - price) / first_price * 100)
        current_step = int(drop_pct // drop_interval_pct)
        next_step = (max(bought_steps) + 1) if bought_steps else 1
        next_buy_price = first_price * (1 - (drop_interval_pct * next_step) / 100)
    next_tp_price = avg_price * (1 + take_profit_pct / 100) if avg_price > 0 else 0.0

    return {
        'raw_unit_amount': raw_unit,
        'adjusted_unit_amount': adjusted,
        'unit_shares': float(shares),
        'remaining_investable': remaining,
        'profit_pct': profit_pct,
        'current_step': current_step,
        'next_buy_price': next_buy_price,
        'next_take_profit_price': next_tp_price,
        'drop_interval_pct': drop_interval_pct,
        'take_profit_pct': take_profit_pct,
    }


def _orders_chrono(position_id: int) -> list[dict[str, Any]]:
    rows = db.list_orders(position_id=position_id, limit=200)
    rows.reverse()  # 오래된 → 최신 순
    return rows


def _realized_pnl(row: dict[str, Any]) -> float:
    if row.get('action') != 'SELL':
        return 0.0
    return to_float(row.get('amount')) - to_float(row.get('quantity')) * to_float(row.get('avg_price'))


def _asset_curve(rows: list[dict[str, Any]]) -> list[float]:
    points: list[float] = []
    cash = config.TOTAL_CAPITAL
    quantity = 0.0
    for row in rows:
        price = to_float(row.get('price'))
        row_q = to_float(row.get('quantity'))
        amount = to_float(row.get('amount'))
        if row.get('action') == 'BUY':
            cash -= amount
            quantity += row_q
        elif row.get('action') == 'SELL':
            cash += amount
            quantity = max(0.0, quantity - row_q)
        points.append(max(0.0, cash + quantity * price))
    return points


# ---- 페이로드 빌더 -----------------------------------------------------------

def build_dashboard_payload(state_bag: 'DashboardState') -> dict[str, Any]:
    position = _primary_position()

    if position is None:
        symbol_label = '-'
        state: dict[str, Any] = {}
        params: dict[str, Any] = {}
        budget = 0.0
        rows: list[dict[str, Any]] = []
        price = 0.0
    else:
        symbol_label = position['ticker']
        state = position['state'] or {}
        params = position['params'] or {}
        budget = float(position['budget'])
        rows = _orders_chrono(int(position['id']))
        last_traded = to_float(rows[-1].get('price')) if rows else 0.0
        live_price = state_bag.last_price if state_bag.last_price else 0.0
        state_price = to_float(state.get('first_price')) or to_float(state.get('avg_price'))
        price = live_price or last_traded or state_price

    metrics = _calc_metrics(state, price, params, budget)

    quantity = to_float(state.get('quantity'))
    avg_price = to_float(state.get('avg_price'))
    invested = to_float(state.get('invested_amount'))
    first_price = to_float(state.get('first_price'))
    market_value = quantity * price
    unrealized = market_value - invested

    sell_rows = [r for r in rows if r.get('action') == 'SELL']
    buy_rows = [r for r in rows if r.get('action') == 'BUY']
    profit_pcts = [to_float(r.get('profit_pct')) for r in sell_rows]
    realized = sum(_realized_pnl(r) for r in sell_rows)
    wins = sum(1 for v in profit_pcts if v > 0)
    losses = sum(1 for v in profit_pcts if v < 0)
    max_invested = max([to_float(r.get('invested_amount')) for r in rows] + [invested, 0.0])

    cash = max(0.0, config.TOTAL_CAPITAL + realized - invested)
    total_asset = cash + market_value
    investable_pct = (budget / config.TOTAL_CAPITAL * 100) if config.TOTAL_CAPITAL else 0.0
    available = max(0.0, budget - invested)
    asset_curve = _asset_curve(rows)
    max_asset = max(asset_curve + [total_asset, config.TOTAL_CAPITAL])
    mdd = ((total_asset - max_asset) / max_asset * 100) if max_asset else 0.0

    current_step = int(metrics['current_step'])
    market = market_status_text()
    status = state_bag.status
    busy = state_bag.busy

    next_run_text = '대기'
    if busy:
        next_run_text = '실행 중'
    elif status == 'RUNNING' and state_bag.next_run_at:
        remaining = max(0, int(state_bag.next_run_at - time.time()))
        next_run_text = f'{remaining}초 후'

    summary_cards = [
        {'label': '현재 수익률', 'value': pct(metrics['profit_pct'], signed=True),
         'subValue': signed_money(unrealized), 'tone': 'green' if unrealized >= 0 else 'red'},
        {'label': '현재 단계', 'value': f'{current_step}단계',
         'subValue': '보유 중' if quantity else '대기', 'tone': 'blue'},
        {'label': '현재 자금 비중',
         'value': pct((invested / total_asset * 100) if total_asset else 0.0),
         'subValue': '', 'tone': 'yellow'},
        {'label': '다음 추가매수', 'value': money(metrics['next_buy_price']),
         'subValue': f'-{(current_step + 1) * metrics["drop_interval_pct"]:.2f}%', 'tone': 'yellow'},
        {'label': '다음 익절', 'value': money(metrics['next_take_profit_price']),
         'subValue': pct(metrics['take_profit_pct'], signed=True), 'tone': 'green'},
        {'label': '현재가', 'value': money(price), 'subValue': symbol_label, 'tone': 'price'},
        {'label': '평단가', 'value': money(avg_price), 'subValue': '', 'tone': 'price'},
        {'label': '보유 수량', 'value': qty(quantity), 'subValue': symbol_label, 'tone': 'price'},
    ]

    total_asset_pct = ((total_asset - config.TOTAL_CAPITAL) / config.TOTAL_CAPITAL * 100) \
        if config.TOTAL_CAPITAL else 0.0
    realized_pct = (realized / config.TOTAL_CAPITAL * 100) if config.TOTAL_CAPITAL else 0.0
    unrealized_pct = (unrealized / invested * 100) if invested else 0.0

    account_rows = [
        {'label': '총 자산', 'amount': money(total_asset),
         'amountClass': 'green-text' if total_asset_pct >= 0 else 'tone-red',
         'note': pct(total_asset_pct, signed=True),
         'noteClass': 'green-text' if total_asset_pct >= 0 else 'tone-red',
         'ratio': '100.00%'},
        {'label': '예수금', 'amount': money(cash), 'amountClass': '',
         'note': '+0.00%', 'noteClass': 'muted',
         'ratio': pct((cash / total_asset * 100) if total_asset else 0.0)},
        {'label': '자산 매수 가능', 'amount': money(budget), 'amountClass': '',
         'note': '+0.00%', 'noteClass': 'muted', 'ratio': pct(investable_pct)},
        {'label': '현재 자산 투입', 'amount': money(invested), 'amountClass': '',
         'note': '+0.00%', 'noteClass': 'muted',
         'ratio': pct((invested / total_asset * 100) if total_asset else 0.0)},
        {'label': '투입 가능 잔액', 'amount': money(available), 'amountClass': '',
         'note': '+0.00%', 'noteClass': 'muted',
         'ratio': pct((available / budget * 100) if budget else 0.0)},
        {'label': '현재 미실현손익', 'amount': signed_money(unrealized),
         'amountClass': 'green-text' if unrealized >= 0 else 'tone-red',
         'note': pct(unrealized_pct, signed=True),
         'noteClass': 'green-text' if unrealized >= 0 else 'tone-red',
         'ratio': pct((unrealized / total_asset * 100) if total_asset else 0.0)},
        {'label': '누적 실현손익', 'amount': signed_money(realized),
         'amountClass': 'green-text' if realized >= 0 else 'tone-red',
         'note': pct(realized_pct, signed=True),
         'noteClass': 'green-text' if realized >= 0 else 'tone-red',
         'ratio': pct(realized_pct)},
        {'label': '최대 자산', 'amount': money(max_asset), 'amountClass': '',
         'note': '+0.00%', 'noteClass': 'muted', 'ratio': '100.00%'},
        {'label': 'MDD', 'amount': pct(mdd),
         'amountClass': 'tone-red' if mdd < 0 else '',
         'note': '', 'noteClass': 'muted', 'ratio': pct(mdd)},
    ]

    position_payload = {
        'symbol': symbol_label,
        'currentPrice': money(price),
        'avgPrice': money(avg_price),
        'quantity': qty(quantity),
        'investedAmount': money(invested),
        'investedPct': pct((invested / total_asset * 100) if total_asset else 0.0),
        'currentProfit': signed_money(unrealized),
        'currentProfitPct': pct(metrics['profit_pct'], signed=True),
        'currentStep': f'{current_step}단계',
        'firstPrice': money(first_price),
        'rawUnitAmount': money(metrics['raw_unit_amount']),
        'adjustedUnitAmount': money(metrics['adjusted_unit_amount']),
        'unitShares': qty(metrics['unit_shares']),
        'nextBuyPrice': money(metrics['next_buy_price']),
        'nextBuyNote': f'-{(current_step + 1) * metrics["drop_interval_pct"]:.2f}%',
        'nextTakeProfitPrice': money(metrics['next_take_profit_price']),
        'nextTakeProfitNote': pct(metrics['take_profit_pct'], signed=True),
        'realized': signed_money(realized),
        'realizedPct': pct(realized_pct, signed=True),
        'tradeCount': str(len(rows)),
        'buyCount': str(len(buy_rows)),
        'sellCount': str(len(sell_rows)),
        'winCount': str(wins),
        'lossCount': str(losses),
        'winRate': pct((wins / len(sell_rows) * 100) if sell_rows else 0.0),
        'avgCyclePct': pct(sum(profit_pcts) / len(profit_pcts) if profit_pcts else 0.0, signed=True),
        'bestCyclePct': pct(max(profit_pcts) if profit_pcts else 0.0, signed=True),
        'worstCyclePct': pct(min(profit_pcts) if profit_pcts else 0.0, signed=True),
        'maxInvestPct': pct((max_invested / config.TOTAL_CAPITAL * 100) if config.TOTAL_CAPITAL else 0.0),
    }

    avg_cycle_pct = (sum(profit_pcts) / len(profit_pcts)) if profit_pcts else 0.0
    performance_rows = [
        {'label': '완료 사이클', 'value': str(len(sell_rows))},
        {'label': '총 매수', 'value': str(len(buy_rows))},
        {'label': '총 매도', 'value': str(len(sell_rows))},
        {'label': '누적 실현손익', 'value': signed_money(realized),
         'tone': 'green' if realized >= 0 else 'red'},
        {'label': '누적 수익률', 'value': pct(realized_pct, signed=True),
         'tone': 'green' if realized_pct >= 0 else 'red'},
        {'label': '승률', 'value': pct((wins / len(sell_rows) * 100) if sell_rows else 0.0),
         'tone': 'green'},
        {'label': '평균 사이클 수익률', 'value': pct(avg_cycle_pct, signed=True),
         'tone': 'green' if avg_cycle_pct >= 0 else 'red'},
        {'label': '최고 사이클 수익률',
         'value': pct(max(profit_pcts) if profit_pcts else 0.0, signed=True), 'tone': 'green'},
        {'label': '최저 사이클 수익률',
         'value': pct(min(profit_pcts) if profit_pcts else 0.0, signed=True),
         'tone': 'green' if (not profit_pcts or min(profit_pcts) >= 0) else 'red'},
        {'label': '최대 자금 비중',
         'value': pct((max_invested / config.TOTAL_CAPITAL * 100) if config.TOTAL_CAPITAL else 0.0)},
        {'label': '현재 자금 비중',
         'value': pct((invested / total_asset * 100) if total_asset else 0.0)},
        {'label': 'MDD', 'value': pct(mdd)},
    ]

    top_actions = [
        {'key': 'start',    'label': '시작',     'icon': 'play',
         'variant': 'disabled' if status == 'RUNNING' else 'run'},
        {'key': 'pause',    'label': '일시정지', 'icon': 'pause',
         'variant': 'pause' if status == 'RUNNING' else 'disabled'},
        {'key': 'run-once', 'label': '1회 실행', 'icon': 'spark',
         'variant': 'disabled' if busy else 'run'},
        {'key': 'refresh',  'label': '새로고침', 'icon': 'refresh', 'variant': 'refresh'},
        {'key': 'close',    'label': '종료',     'icon': 'x',
         'variant': 'disabled' if status == 'STOPPED' else 'end'},
    ]

    trades = []
    for row in reversed(rows[-20:]):
        trades.append({
            'time': compact_time(row.get('ts', '')),
            'action': row.get('action', '-'),
            'symbol': row.get('ticker') or symbol_label,
            'price': money(to_float(row.get('price'))),
            'quantity': qty(to_float(row.get('quantity'))),
            'amount': money(to_float(row.get('amount'))),
            'avgPrice': money(to_float(row.get('avg_price'))),
            'profitPct': pct(to_float(row.get('profit_pct')), signed=True),
            'step': str(row.get('step') or '0'),
            'reason': row.get('reason') or '-',
        })

    execution_status = state_bag.execution_status(market)
    kill_switch = safety.kill_switch_status()
    enabled_count = len([p for p in db.list_positions() if p['enabled']])
    ks_value = '비활성'
    if kill_switch['active']:
        ks_value = f"활성 — {kill_switch['reason']}" if kill_switch['reason'] else '활성'
    system_rows = [
        {'label': '실행 단계',          'value': execution_status['phaseLabel']},
        {'label': '마지막 신호',        'value': execution_status['lastSignal']},
        {'label': '마지막 가격조회',    'value': execution_status['lastPriceCheckAt']},
        {'label': '마지막 오류',        'value': execution_status['lastError'] or '-'},
        {'label': 'Kill switch',        'value': ks_value},
        {'label': '장 시간 차단',       'value': '활성' if config.MARKET_HOURS_STRICT else '비활성'},
        {'label': '일일 손실 한도',
         'value': f'{config.DAILY_LOSS_LIMIT_PCT:.2f}%' if config.DAILY_LOSS_LIMIT_PCT > 0 else '비활성'},
        {'label': '주문 멱등성 윈도우',
         'value': f'{config.ORDER_IDEMPOTENCY_WINDOW_SEC}초' if config.ORDER_IDEMPOTENCY_WINDOW_SEC > 0 else '비활성'},
        {'label': 'MODE',               'value': config.BROKER},
        {'label': '자산 개수',          'value': f'{enabled_count}개'},
        {'label': '현재 시장 상태',     'value': market},
        {'label': '데이터 소스',        'value': f'SQLite + {config.BROKER}'},
        {'label': '대시보드 조회 주기', 'value': f'{config.DASHBOARD_REFRESH_SEC}초'},
        {'label': '가격 조회 주기',     'value': f'{config.PRICE_REFRESH_SEC}초'},
        {'label': '전략 실행 주기',     'value': f'{config.ENGINE_INTERVAL_SECONDS}초'},
        {'label': '마지막 주문 실행',   'value': state_bag.last_run_time},
        {'label': '마지막 가격 업데이트', 'value': state_bag.last_price_time},
        {'label': '다음 실행까지',      'value': next_run_text},
    ]

    return {
        'appName': 'MMK 자동매매 대시보드',
        'mode': config.BROKER,
        'status': 'RUNNING' if busy else status,
        'symbol': symbol_label,
        'marketStatus': market,
        'lastRunTime': state_bag.last_run_time,
        'lastPriceTime': state_bag.last_price_time,
        'nextRunRemaining': next_run_text,
        'refreshSec': config.ENGINE_INTERVAL_SECONDS,
        'strategyRunSec': config.ENGINE_INTERVAL_SECONDS,
        'priceRefreshSec': config.PRICE_REFRESH_SEC,
        'dashboardRefreshSec': config.DASHBOARD_REFRESH_SEC,
        'topActions': top_actions,
        'summaryCards': summary_cards,
        'accountRows': account_rows,
        'systemRows': system_rows,
        'messages': list(reversed(state_bag.messages[-40:])),
        'position': position_payload,
        'performanceRows': performance_rows,
        'tradeTabs': [{'key': 'trades',   'label': '최근 거래 로그'},
                      {'key': 'messages', 'label': '상태 메시지'}],
        'trades': trades,
        'executionStatus': execution_status,
        'killSwitch': kill_switch,
        'safety': {
            'marketHoursStrict': config.MARKET_HOURS_STRICT,
            'dailyLossLimitPct': config.DAILY_LOSS_LIMIT_PCT,
            'idempotencyWindowSec': config.ORDER_IDEMPOTENCY_WINDOW_SEC,
        },
    }


# ---- DashboardState (스레드 안전 컨트롤 + 메시지 버퍼) -----------------------

class DashboardState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.status: Literal['WAITING', 'RUNNING', 'STOPPED'] = 'WAITING'
        self.busy = False
        self.phase = 'idle'
        self.last_started_at = '-'
        self.last_finished_at = '-'
        self.last_price_check_at = '-'
        self.last_price = 0.0
        self.last_signal = '-'
        self.last_order_action = '-'
        self.last_order_text = f'{config.BROKER} order 없음'
        self.last_error = ''
        self.next_run_at = 0.0
        self.stop_event = threading.Event()
        self.loop_thread: threading.Thread | None = None
        self._broker: Broker | None = None
        now = datetime.now().strftime('%H:%M:%S')
        self.last_run_time = '-'
        self.last_price_time = now
        self.messages: list[str] = [f'{now}  백엔드 시작 — {config.BROKER} 브로커 준비']

    def _now(self) -> str:
        return datetime.now().strftime('%H:%M:%S')

    def _append_message(self, message: str) -> None:
        self.messages.append(f'{self._now()}  {message}')
        self.messages = self.messages[-40:]

    def _phase_label(self) -> str:
        labels = {
            'idle': '대기',
            'price_lookup': '가격 조회 중',
            'strategy': '전략 판단 중',
            'order': '주문 기록',
            'waiting': '다음 실행 대기',
            'error': '오류',
            'stopped': '종료',
        }
        return labels.get(self.phase, self.phase)

    def _ensure_broker(self) -> Broker:
        if self._broker is None:
            self._broker = get_broker()
        return self._broker

    def execution_status(self, market: str) -> dict[str, Any]:
        next_run_text = '대기'
        if self.busy:
            next_run_text = '실행 중'
        elif self.status == 'RUNNING' and self.next_run_at:
            remaining = max(0, int(self.next_run_at - time.time()))
            next_run_text = f'{remaining}초 후'
        return {
            'phase': self.phase,
            'phaseLabel': self._phase_label(),
            'isRunning': self.status == 'RUNNING',
            'isBusy': self.busy,
            'lastStartedAt': self.last_started_at,
            'lastFinishedAt': self.last_finished_at,
            'lastPriceCheckAt': self.last_price_check_at,
            'lastPrice': money(self.last_price) if self.last_price else '-',
            'lastSignal': self.last_signal,
            'lastOrderAction': self.last_order_action,
            'lastOrderText': self.last_order_text,
            'lastError': self.last_error,
            'nextRunText': next_run_text,
            'source': f'SQLite + {config.BROKER}',
            'market': market,
        }

    def _execute_cycle_locked(self) -> None:
        if self.busy:
            self._append_message('이전 실행이 아직 끝나지 않았습니다.')
            return
        self.busy = True
        self.phase = 'price_lookup'
        self.last_started_at = self._now()
        self.last_error = ''
        self.last_order_action = '-'
        self.last_order_text = 'no order'
        try:
            self._append_message('활성 종목 사이클 시작')
            broker = self._ensure_broker()
            results = run_cycle(broker)

            now = self._now()
            self.last_run_time = now
            self.last_price_time = now
            self.last_price_check_at = now

            if not results:
                self.phase = 'waiting'
                self._append_message('활성 종목이 없습니다. /api/positions로 추가하세요.')
                return

            # blocked 사유는 모든 종목에 대해 메시지로 누적 출력
            for r in results:
                if r.get('blocked'):
                    self._append_message(f"[{r.get('ticker', '?')}] BLOCKED — {r['blocked']}")

            first = results[0]
            if 'error' in first:
                raise RuntimeError(first['error'])

            self.last_price = to_float(first.get('current_price'))
            signal = first.get('signal') or {}
            order = first.get('order')
            blocked = first.get('blocked')
            self.phase = 'strategy'
            self.last_signal = str(signal.get('action', 'HOLD'))
            if order:
                self.phase = 'order'
                self.last_order_action = str(order.get('action', '-'))
                self.last_order_text = (
                    f"{self.last_order_action} {to_float(order.get('quantity')):.6f} shares @ "
                    f"{money(to_float(order.get('price')))}"
                )
                self._append_message(f'{self.last_order_text} — {config.BROKER} 주문 기록')
            elif blocked:
                self.phase = 'waiting'
                self.last_order_text = f'BLOCKED: {blocked}'
            else:
                self.phase = 'waiting'
                self._append_message(f"{signal.get('action', 'HOLD')}: {signal.get('reason', '')}")
        except Exception as exc:
            self.phase = 'error'
            self.last_error = str(exc)
            self._append_message(f'ERROR: {exc}')
        finally:
            self.last_finished_at = self._now()
            self.busy = False

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            with self.lock:
                if self.status != 'RUNNING':
                    break
                self._execute_cycle_locked()
                self.next_run_at = time.time() + int(config.ENGINE_INTERVAL_SECONDS)
            self.stop_event.wait(int(config.ENGINE_INTERVAL_SECONDS))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return build_dashboard_payload(self)

    def start(self) -> dict[str, Any]:
        with self.lock:
            if config.BROKER != 'mock':
                self._append_message('Phase 1에서는 mock 브로커만 자동 루프를 지원합니다.')
                return self.snapshot()
            if self.status == 'RUNNING':
                self._append_message('이미 자동매매 루프 실행 중입니다.')
                return self.snapshot()
            self.status = 'RUNNING'
            self.phase = 'waiting'
            self.next_run_at = time.time()
            self.stop_event.clear()
            self._append_message('자동매매 루프 시작')
            self.loop_thread = threading.Thread(target=self._loop, daemon=True)
            self.loop_thread.start()
            return self.snapshot()

    def pause(self) -> dict[str, Any]:
        with self.lock:
            self.status = 'WAITING'
            self.phase = 'idle'
            self.next_run_at = 0.0
            self.stop_event.set()
            self._append_message('자동매매 루프 일시정지')
            return self.snapshot()

    def run_once(self) -> dict[str, Any]:
        with self.lock:
            self._execute_cycle_locked()
            if self.status == 'STOPPED':
                self.status = 'WAITING'
            return self.snapshot()

    def refresh(self) -> dict[str, Any]:
        with self.lock:
            self.last_price_time = self._now()
            self._append_message('새로고침 — DB 재조회')
            return self.snapshot()

    def close(self) -> dict[str, Any]:
        with self.lock:
            self.status = 'STOPPED'
            self.phase = 'stopped'
            self.next_run_at = 0.0
            self.stop_event.set()
            self._append_message('종료 요청 처리')
            return self.snapshot()

    def note(self, message: str) -> None:
        """외부에서 메시지 버퍼에 한 줄 남길 때 사용 (kill switch 등)."""
        with self.lock:
            self._append_message(message)

    def pause_quiet(self) -> None:
        """비상 정지 시 자동 루프만 멈춘다 (별도 메시지 없이)."""
        with self.lock:
            if self.status == 'RUNNING':
                self.status = 'WAITING'
            self.phase = 'idle' if self.phase != 'error' else self.phase
            self.next_run_at = 0.0
            self.stop_event.set()


STATE = DashboardState()


def _ctrl(action: str, message: str, data: dict[str, Any], ok: bool = True) -> dict[str, Any]:
    return {'ok': ok, 'action': action, 'message': message, 'dashboard': data}


@router.get('/api/dashboard')
def get_dashboard():
    return STATE.snapshot()


@router.post('/api/control/start')
def control_start():
    return _ctrl('start', '시작 버튼: 자동매매 루프를 시작했습니다.', STATE.start())


@router.post('/api/control/pause')
def control_pause():
    return _ctrl('pause', '일시정지 버튼: 자동매매 루프를 멈췄습니다.', STATE.pause())


@router.post('/api/control/run-once')
def control_run_once():
    return _ctrl('run-once', '1회 실행 버튼: 활성 종목 사이클을 실행했습니다.', STATE.run_once())


@router.post('/api/control/refresh')
def control_refresh():
    return _ctrl('refresh', '새로고침: DB에서 최신 상태를 다시 읽었습니다.', STATE.refresh())


@router.post('/api/control/close')
def control_close():
    return _ctrl('close', '종료 버튼: 자동매매 루프를 종료 상태로 변경했습니다.', STATE.close())


@router.post('/api/control/kill-switch')
def control_kill_switch_trip(reason: str = '사용자 수동 비상 정지'):
    safety.trip_kill_switch(reason)
    STATE.note(f'KILL SWITCH 활성: {reason}')
    STATE.pause_quiet()  # 자동 루프 즉시 중단
    return _ctrl('kill-switch', f'비상 정지: {reason}', STATE.snapshot())


@router.post('/api/control/kill-switch/reset')
def control_kill_switch_reset():
    safety.reset_kill_switch()
    STATE.note('KILL SWITCH 해제')
    return _ctrl('kill-switch-reset', '비상 정지 해제. 다음 사이클부터 주문이 다시 실행됩니다.',
                 STATE.snapshot())
