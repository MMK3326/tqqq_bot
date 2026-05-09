import csv
import json
import threading
import time
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from main import run_once as run_strategy_once
from main import select_broker
from security import POSITION_FILE, TRADE_LOG_FILE, ensure_data_dir
from strategy.tqqq_strategy import calculate_metrics
from utils.logger import CSV_ENCODING, ensure_trade_log


app = FastAPI(title='TQQQ Dashboard API', version='0.5.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)


def to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def money(value: float) -> str:
    return f'${value:,.2f}'


def signed_money(value: float) -> str:
    sign = '+' if value >= 0 else '-'
    return f'{sign}${abs(value):,.2f}'


def pct(value: float, signed: bool = False) -> str:
    sign = '+' if signed and value >= 0 else ''
    return f'{sign}{value:.2f}%'


def qty(value: float) -> str:
    return f'{value:.6f}'


def compact_time(value: str) -> str:
    if not value:
        return '-'
    try:
        return datetime.fromisoformat(value).strftime('%H:%M:%S')
    except ValueError:
        return value[-8:] if len(value) >= 8 else value


def market_status() -> str:
    try:
        now = datetime.now(ZoneInfo('America/New_York'))
    except ZoneInfoNotFoundError:
        return '확인불가'

    if now.weekday() >= 5:
        return '장외'

    current = now.time()
    pre = datetime.strptime('04:00', '%H:%M').time()
    regular = datetime.strptime('09:30', '%H:%M').time()
    close = datetime.strptime('16:00', '%H:%M').time()
    after = datetime.strptime('20:00', '%H:%M').time()

    if pre <= current < regular:
        return '프리마켓'
    if regular <= current < close:
        return '정규장'
    if close <= current < after:
        return '애프터마켓'
    return '장외'


def default_position() -> dict[str, Any]:
    return {
        'symbol': config.SYMBOL,
        'quantity': 0.0,
        'avg_price': 0.0,
        'first_price': 0.0,
        'invested_amount': 0.0,
        'bought_steps': [],
        'cycle_count': 0,
    }


def read_position() -> dict[str, Any]:
    ensure_data_dir()
    default = default_position()
    if not POSITION_FILE.exists():
        POSITION_FILE.write_text(json.dumps(default, indent=2, ensure_ascii=False), encoding='utf-8')
        return default
    try:
        data = json.loads(POSITION_FILE.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError):
        return default
    return {**default, **data}


def read_trade_logs() -> list[dict[str, Any]]:
    ensure_trade_log()
    try:
        with TRADE_LOG_FILE.open('r', newline='', encoding=CSV_ENCODING) as file:
            rows = list(csv.DictReader(file))
    except OSError:
        return []

    result = []
    for row in rows:
        item = dict(row)
        item['symbol'] = item.get('symbol') or config.SYMBOL
        result.append(item)
    return result


def safe_metrics(price: float, position: dict[str, Any]) -> dict[str, Any]:
    safe_price = price if price > 0 else max(to_float(position.get('avg_price')), to_float(position.get('first_price')), 1.0)
    return calculate_metrics(
        current_price=safe_price,
        position=position,
        total_capital=config.TOTAL_CAPITAL,
        max_invest_ratio=config.MAX_INVEST_RATIO,
        base_split_count=config.BASE_SPLIT_COUNT,
        drop_interval_pct=config.DROP_INTERVAL_PCT,
        take_profit_pct=config.TAKE_PROFIT_PCT,
        use_integer_share_unit=config.USE_INTEGER_SHARE_UNIT,
    )


def realized_pnl(row: dict[str, Any]) -> float:
    return to_float(row.get('amount')) - to_float(row.get('quantity')) * to_float(row.get('avg_price'))


def cash_from_trade_logs(rows: list[dict[str, Any]], invested: float) -> float:
    realized = sum(realized_pnl(row) for row in rows if row.get('action') == 'SELL')
    return max(0.0, config.TOTAL_CAPITAL + realized - invested)


def estimate_asset_curve(rows: list[dict[str, Any]]) -> list[float]:
    points = []
    cash = config.TOTAL_CAPITAL
    quantity = 0.0
    for row in rows:
        action = row.get('action')
        price = to_float(row.get('price'))
        row_quantity = to_float(row.get('quantity'))
        amount = to_float(row.get('amount'))

        if action == 'BUY':
            cash -= amount
            quantity += row_quantity
        elif action == 'SELL':
            cash += amount
            quantity = max(0.0, quantity - row_quantity)

        points.append(max(0.0, cash + quantity * price))
    return points


def symbol_stats(position: dict[str, Any], rows: list[dict[str, Any]], price: float, metrics: dict[str, Any]) -> dict[str, Any]:
    quantity = to_float(position.get('quantity'))
    avg_price = to_float(position.get('avg_price'))
    invested = to_float(position.get('invested_amount'))
    first_price = to_float(position.get('first_price'))
    market_value = quantity * price
    unrealized = market_value - invested
    sell_rows = [row for row in rows if row.get('action') == 'SELL']
    buy_rows = [row for row in rows if row.get('action') == 'BUY']
    profit_pcts = [to_float(row.get('profit_pct')) for row in sell_rows]
    realized = sum(realized_pnl(row) for row in sell_rows)
    wins = sum(1 for value in profit_pcts if value > 0)
    losses = sum(1 for value in profit_pcts if value < 0)
    max_invested = max([to_float(row.get('invested_amount')) for row in rows] + [invested, 0.0])

    return {
        'symbol': config.SYMBOL,
        'price': price,
        'first_price': first_price,
        'avg_price': avg_price,
        'quantity': quantity,
        'invested': invested,
        'market_value': market_value,
        'unrealized': unrealized,
        'unrealized_pct': unrealized / invested * 100 if invested else 0.0,
        'current_step': len(position.get('bought_steps') or []),
        'next_buy': metrics.get('next_buy_price', 0.0),
        'next_sell': metrics.get('next_take_profit_price', 0.0),
        'raw_unit': metrics.get('raw_unit_amount', 0.0),
        'adjusted_unit': metrics.get('adjusted_unit_amount', 0.0),
        'unit_shares': metrics.get('unit_shares', 0.0),
        'realized': realized,
        'realized_pct': realized / config.TOTAL_CAPITAL * 100 if config.TOTAL_CAPITAL else 0.0,
        'trade_count': len(rows),
        'buy_count': len(buy_rows),
        'sell_count': len(sell_rows),
        'wins': wins,
        'losses': losses,
        'win_rate': wins / len(sell_rows) * 100 if sell_rows else 0.0,
        'avg_cycle_pct': sum(profit_pcts) / len(profit_pcts) if profit_pcts else 0.0,
        'best_cycle_pct': max(profit_pcts) if profit_pcts else 0.0,
        'worst_cycle_pct': min(profit_pcts) if profit_pcts else 0.0,
        'max_invest_pct': max_invested / config.TOTAL_CAPITAL * 100 if config.TOTAL_CAPITAL else 0.0,
    }


def account_summary(symbol: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    invested = symbol['invested']
    market_value = symbol['market_value']
    cash = cash_from_trade_logs(rows, invested)
    total_asset = cash + market_value
    investable = config.TOTAL_CAPITAL * config.MAX_INVEST_RATIO
    available = max(0.0, investable - invested)
    max_asset = max(estimate_asset_curve(rows) + [total_asset, config.TOTAL_CAPITAL])
    mdd = (total_asset - max_asset) / max_asset * 100 if max_asset else 0.0
    return {
        'total_asset': total_asset,
        'total_asset_pct': (total_asset - config.TOTAL_CAPITAL) / config.TOTAL_CAPITAL * 100 if config.TOTAL_CAPITAL else 0.0,
        'cash': cash,
        'cash_pct': cash / total_asset * 100 if total_asset else 0.0,
        'invested': invested,
        'invested_pct': invested / total_asset * 100 if total_asset else 0.0,
        'investable': investable,
        'investable_pct': config.MAX_INVEST_RATIO * 100,
        'available': available,
        'available_pct': available / investable * 100 if investable else 0.0,
        'unrealized': symbol['unrealized'],
        'unrealized_pct': symbol['unrealized_pct'],
        'realized': symbol['realized'],
        'realized_pct': symbol['realized_pct'],
        'max_asset': max_asset,
        'mdd': mdd,
    }


def normalize_reason(row: dict[str, Any]) -> str:
    action = row.get('action', '-')
    step = row.get('step', '0')
    if action == 'SELL':
        return '평단가 대비 익절'
    if action == 'BUY' and str(step) == '0':
        return '초기 1분할 매수'
    if action == 'BUY':
        return f'{step}분할 추가매수'
    return row.get('reason') or '-'


def build_trade_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    trades = []
    for row in reversed(rows[-20:]):
        trades.append(
            {
                'time': compact_time(row.get('time', '')),
                'action': row.get('action', '-'),
                'symbol': row.get('symbol') or config.SYMBOL,
                'price': money(to_float(row.get('price'))),
                'quantity': qty(to_float(row.get('quantity'))),
                'amount': money(to_float(row.get('amount'))),
                'avgPrice': money(to_float(row.get('avg_price'))),
                'profitPct': pct(to_float(row.get('profit_pct')), signed=True),
                'step': str(row.get('step') or '0'),
                'reason': normalize_reason(row),
            }
        )
    return trades


def build_actions(status: str, busy: bool) -> list[dict[str, str]]:
    running = status == 'RUNNING'
    stopped = status == 'STOPPED'
    return [
        {'key': 'start', 'label': '시작', 'icon': 'play', 'variant': 'disabled' if running else 'run'},
        {'key': 'pause', 'label': '일시정지', 'icon': 'pause', 'variant': 'pause' if running else 'disabled'},
        {'key': 'run-once', 'label': '1회 실행', 'icon': 'spark', 'variant': 'disabled' if busy else 'run'},
        {'key': 'refresh', 'label': '새로고침', 'icon': 'refresh', 'variant': 'refresh'},
        {'key': 'close', 'label': '종료', 'icon': 'x', 'variant': 'disabled' if stopped else 'end'},
    ]


def latest_display_price(position: dict[str, Any], rows: list[dict[str, Any]]) -> float:
    price = to_float(position.get('first_price')) or to_float(position.get('avg_price'))
    if rows:
        price = to_float(rows[-1].get('price')) or price
    if to_float(position.get('quantity')) > 0 and to_float(position.get('avg_price')) > 0:
        price = max(price, to_float(position.get('first_price')), to_float(position.get('avg_price')))
    return price


def build_dashboard_payload(
    status: str,
    busy: bool,
    messages: list[str],
    last_run_time: str,
    last_price_time: str,
) -> dict[str, Any]:
    position = read_position()
    rows = read_trade_logs()
    price = latest_display_price(position, rows)
    metrics = safe_metrics(price, position)
    symbol = symbol_stats(position, rows, price, metrics)
    account = account_summary(symbol, rows)
    current_step = int(symbol['current_step'])
    market = market_status()

    account_rows = [
        {'label': '총 자산', 'amount': money(account['total_asset']), 'amountClass': 'green-text' if account['total_asset_pct'] >= 0 else 'tone-red', 'note': pct(account['total_asset_pct'], signed=True), 'noteClass': 'green-text' if account['total_asset_pct'] >= 0 else 'tone-red', 'ratio': '100.00%'},
        {'label': '예수금', 'amount': money(account['cash']), 'amountClass': '', 'note': '+0.00%', 'noteClass': 'muted', 'ratio': pct(account['cash_pct'])},
        {'label': '자산 매수 가능', 'amount': money(account['investable']), 'amountClass': '', 'note': '+0.00%', 'noteClass': 'muted', 'ratio': pct(account['investable_pct'])},
        {'label': '현재 자산 투입', 'amount': money(account['invested']), 'amountClass': '', 'note': '+0.00%', 'noteClass': 'muted', 'ratio': pct(account['invested_pct'])},
        {'label': '투입 가능 잔액', 'amount': money(account['available']), 'amountClass': '', 'note': '+0.00%', 'noteClass': 'muted', 'ratio': pct(account['available_pct'])},
        {'label': '현재 미실현손익', 'amount': signed_money(account['unrealized']), 'amountClass': 'green-text' if account['unrealized'] >= 0 else 'tone-red', 'note': pct(account['unrealized_pct'], signed=True), 'noteClass': 'green-text' if account['unrealized'] >= 0 else 'tone-red', 'ratio': pct(account['unrealized'] / account['total_asset'] * 100 if account['total_asset'] else 0.0)},
        {'label': '누적 실현손익', 'amount': signed_money(account['realized']), 'amountClass': 'green-text' if account['realized'] >= 0 else 'tone-red', 'note': pct(account['realized_pct'], signed=True), 'noteClass': 'green-text' if account['realized'] >= 0 else 'tone-red', 'ratio': pct(account['realized_pct'])},
        {'label': '최대 자산', 'amount': money(account['max_asset']), 'amountClass': '', 'note': '+0.00%', 'noteClass': 'muted', 'ratio': '100.00%'},
        {'label': 'MDD', 'amount': pct(account['mdd']), 'amountClass': 'tone-red' if account['mdd'] < 0 else '', 'note': '', 'noteClass': 'muted', 'ratio': pct(account['mdd'])},
    ]

    position_payload = {
        'symbol': config.SYMBOL,
        'currentPrice': money(symbol['price']),
        'avgPrice': money(symbol['avg_price']),
        'quantity': qty(symbol['quantity']),
        'investedAmount': money(symbol['invested']),
        'investedPct': pct(account['invested_pct']),
        'currentProfit': signed_money(symbol['unrealized']),
        'currentProfitPct': pct(symbol['unrealized_pct'], signed=True),
        'currentStep': f'{current_step}단계',
        'firstPrice': money(symbol['first_price']),
        'rawUnitAmount': money(symbol['raw_unit']),
        'adjustedUnitAmount': money(symbol['adjusted_unit']),
        'unitShares': qty(symbol['unit_shares']),
        'nextBuyPrice': money(symbol['next_buy']),
        'nextBuyNote': f'-{(current_step + 1) * config.DROP_INTERVAL_PCT:.2f}%',
        'nextTakeProfitPrice': money(symbol['next_sell']),
        'nextTakeProfitNote': pct(config.TAKE_PROFIT_PCT, signed=True),
        'realized': signed_money(symbol['realized']),
        'realizedPct': pct(symbol['realized_pct'], signed=True),
        'tradeCount': str(symbol['trade_count']),
        'buyCount': str(symbol['buy_count']),
        'sellCount': str(symbol['sell_count']),
        'winCount': str(symbol['wins']),
        'lossCount': str(symbol['losses']),
        'winRate': pct(symbol['win_rate']),
        'avgCyclePct': pct(symbol['avg_cycle_pct'], signed=True),
        'bestCyclePct': pct(symbol['best_cycle_pct'], signed=True),
        'worstCyclePct': pct(symbol['worst_cycle_pct'], signed=True),
        'maxInvestPct': pct(symbol['max_invest_pct']),
    }

    performance_rows = [
        {'label': '완료 사이클', 'value': str(symbol['sell_count'])},
        {'label': '총 매수', 'value': str(symbol['buy_count'])},
        {'label': '총 매도', 'value': str(symbol['sell_count'])},
        {'label': '누적 실현손익', 'value': signed_money(symbol['realized']), 'tone': 'green' if symbol['realized'] >= 0 else 'red'},
        {'label': '누적 수익률', 'value': pct(symbol['realized_pct'], signed=True), 'tone': 'green' if symbol['realized_pct'] >= 0 else 'red'},
        {'label': '승률', 'value': pct(symbol['win_rate']), 'tone': 'green'},
        {'label': '평균 사이클 수익률', 'value': pct(symbol['avg_cycle_pct'], signed=True), 'tone': 'green' if symbol['avg_cycle_pct'] >= 0 else 'red'},
        {'label': '최고 사이클 수익률', 'value': pct(symbol['best_cycle_pct'], signed=True), 'tone': 'green'},
        {'label': '최저 사이클 수익률', 'value': pct(symbol['worst_cycle_pct'], signed=True), 'tone': 'green' if symbol['worst_cycle_pct'] >= 0 else 'red'},
        {'label': '최대 자금 비중', 'value': pct(symbol['max_invest_pct'])},
        {'label': '현재 자금 비중', 'value': pct(account['invested_pct'])},
        {'label': 'MDD', 'value': pct(account['mdd'])},
    ]

    return {
        'appName': 'MMK 자동매매 대시보드',
        'mode': config.MODE,
        'status': 'RUNNING' if busy else status,
        'symbol': config.SYMBOL,
        'marketStatus': market,
        'lastRunTime': last_run_time,
        'lastPriceTime': last_price_time,
        'nextRunRemaining': f'{config.STRATEGY_RUN_INTERVAL_SEC}초' if status == 'RUNNING' else '대기',
        'refreshSec': config.STRATEGY_RUN_INTERVAL_SEC,
        'strategyRunSec': config.STRATEGY_RUN_INTERVAL_SEC,
        'priceRefreshSec': config.PRICE_REFRESH_SEC,
        'dashboardRefreshSec': config.DASHBOARD_REFRESH_SEC,
        'topActions': build_actions(status, busy),
        'summaryCards': [
            {'label': '현재 수익률', 'value': pct(symbol['unrealized_pct'], signed=True), 'subValue': signed_money(symbol['unrealized']), 'tone': 'green' if symbol['unrealized'] >= 0 else 'red'},
            {'label': '현재 단계', 'value': f'{current_step}단계', 'subValue': '보유 중' if symbol['quantity'] else '대기', 'tone': 'blue'},
            {'label': '현재 자금 비중', 'value': pct(account['invested_pct']), 'subValue': '', 'tone': 'yellow'},
            {'label': '다음 추가매수', 'value': money(symbol['next_buy']), 'subValue': f'-{(current_step + 1) * config.DROP_INTERVAL_PCT:.2f}%', 'tone': 'yellow'},
            {'label': '다음 익절', 'value': money(symbol['next_sell']), 'subValue': pct(config.TAKE_PROFIT_PCT, signed=True), 'tone': 'green'},
            {'label': '현재가', 'value': money(symbol['price']), 'subValue': config.SYMBOL, 'tone': 'price'},
            {'label': '평단가', 'value': money(symbol['avg_price']), 'subValue': '', 'tone': 'price'},
            {'label': '보유 수량', 'value': qty(symbol['quantity']), 'subValue': config.SYMBOL, 'tone': 'price'},
        ],
        'accountRows': account_rows,
        'systemRows': [
            {'label': 'MODE', 'value': config.MODE},
            {'label': '자산 개수', 'value': '1개'},
            {'label': '현재 시장 상태', 'value': market},
            {'label': '데이터 소스', 'value': 'yfinance + position/trade_log'},
            {'label': '대시보드 조회 주기', 'value': f'{config.DASHBOARD_REFRESH_SEC}초'},
            {'label': '가격 조회 주기', 'value': f'{config.PRICE_REFRESH_SEC}초'},
            {'label': '전략 실행 주기', 'value': f'{config.STRATEGY_RUN_INTERVAL_SEC}초'},
            {'label': '마지막 주문 실행', 'value': last_run_time},
            {'label': '마지막 가격 업데이트', 'value': last_price_time},
            {'label': '다음 실행까지', 'value': f'{config.STRATEGY_RUN_INTERVAL_SEC}초' if status == 'RUNNING' else '대기'},
        ],
        'messages': list(reversed(messages[-40:])),
        'position': position_payload,
        'performanceRows': performance_rows,
        'tradeTabs': [
            {'key': 'trades', 'label': '최근 거래 로그'},
            {'key': 'messages', 'label': '상태 메시지'},
        ],
        'trades': build_trade_rows(rows),
    }


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
        self.last_order_text = 'mock order 없음'
        self.last_error = ''
        self.next_run_at = 0.0
        self.stop_event = threading.Event()
        self.loop_thread: threading.Thread | None = None
        self.broker = select_broker() if config.MODE == 'mock' else None
        now = datetime.now().strftime('%H:%M:%S')
        self.last_run_time = '-'
        self.last_price_time = now
        self.messages = [f'{now}  실제 파일 데이터 연결 완료']

    def _now(self) -> str:
        return datetime.now().strftime('%H:%M:%S')

    def _append_message(self, message: str) -> None:
        self.messages.append(f'{self._now()}  {message}')
        self.messages = self.messages[-40:]

    def _phase_label(self) -> str:
        labels = {
            'idle': '\ub300\uae30',
            'price_lookup': '\uac00\uaca9 \uc870\ud68c \uc911',
            'strategy': '\uc804\ub7b5 \ud310\ub2e8 \uc911',
            'order': 'mock \uc8fc\ubb38 \uae30\ub85d',
            'waiting': '\ub2e4\uc74c \uc2e4\ud589 \ub300\uae30',
            'error': '\uc624\ub958',
            'stopped': '\uc885\ub8cc',
        }
        return labels.get(self.phase, self.phase)

    def _execution_status_locked(self) -> dict[str, Any]:
        next_run_text = '\ub300\uae30'
        if self.busy:
            next_run_text = '\uc2e4\ud589 \uc911'
        elif self.status == 'RUNNING' and self.next_run_at:
            remaining = max(0, int(self.next_run_at - time.time()))
            next_run_text = f'{remaining}\ucd08 \ud6c4'

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
            'source': 'yfinance + mock_broker',
        }

    def _ensure_mock_mode(self) -> None:
        if config.MODE != 'mock':
            raise RuntimeError('실거래 모드에서는 대시보드 API 실행을 차단했습니다.')

    def _execute_strategy_once_locked(self) -> None:
        self._ensure_mock_mode()
        if self.busy:
            self._append_message('이전 실행이 아직 끝나지 않았습니다.')
            return

        self.busy = True
        self.phase = 'price_lookup'
        self.last_started_at = self._now()
        self.last_error = ''
        self.last_order_action = '-'
        self.last_order_text = 'mock order none'
        try:
            self._append_message('현재가 조회 및 전략 판단 시작')
            self._append_message('PRICE_LOOKUP_START: requesting TQQQ price from yfinance.')
            result = run_strategy_once(self.broker)
            now = self._now()
            self.last_run_time = now
            self.last_price_time = now
            self.last_price_check_at = now
            self.last_price = to_float(result.get('current_price'))

            self.phase = 'strategy'
            signal = result.get('signal') or {}
            order_result = result.get('order_result')
            self.last_signal = str(signal.get('action', 'HOLD'))
            if order_result:
                self.phase = 'order'
                self.last_order_action = str(order_result.get('action', '-'))
                self.last_order_text = (
                    f"{self.last_order_action} "
                    f"{to_float(order_result.get('quantity')):.6f} shares @ "
                    f"{money(to_float(order_result.get('price')))}"
                )
                self._append_message(f'{self.last_order_text} - mock order recorded')
                self._append_message(f"{order_result.get('action', '-')} mock 주문 실행")
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
                self._execute_strategy_once_locked()
                self.next_run_at = time.time() + int(config.STRATEGY_RUN_INTERVAL_SEC)
            self.stop_event.wait(int(config.STRATEGY_RUN_INTERVAL_SEC))

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            data = build_dashboard_payload(self.status, self.busy, list(self.messages), self.last_run_time, self.last_price_time)
            execution_status = self._execution_status_locked()
            data['executionStatus'] = execution_status
            data['systemRows'] = [
                {'label': '\uc2e4\ud589 \ub2e8\uacc4', 'value': execution_status['phaseLabel']},
                {'label': '\ub9c8\uc9c0\ub9c9 \uc2e0\ud638', 'value': execution_status['lastSignal']},
                {'label': '\ub9c8\uc9c0\ub9c9 \uac00\uaca9\uc870\ud68c', 'value': execution_status['lastPriceCheckAt']},
                {'label': '\ub9c8\uc9c0\ub9c9 \uc624\ub958', 'value': execution_status['lastError'] or '-'},
                *data.get('systemRows', []),
            ]
            return data

    def start(self) -> dict[str, Any]:
        with self.lock:
            self._ensure_mock_mode()
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
            self._execute_strategy_once_locked()
            if self.status == 'STOPPED':
                self.status = 'WAITING'
            return self.snapshot()

    def refresh(self) -> dict[str, Any]:
        with self.lock:
            self.last_price_time = self._now()
            self._append_message('새로고침 완료 - position/trade_log 재조회')
            return self.snapshot()

    def close(self) -> dict[str, Any]:
        with self.lock:
            self.status = 'STOPPED'
            self.phase = 'stopped'
            self.next_run_at = 0.0
            self.stop_event.set()
            self._append_message('종료 요청 처리')
            return self.snapshot()


STATE = DashboardState()


def control_response(action: str, message: str, dashboard_data: dict[str, Any], ok: bool = True) -> dict[str, Any]:
    return {'ok': ok, 'action': action, 'message': message, 'dashboard': dashboard_data}


@app.get('/health')
def health() -> dict[str, str]:
    return {'status': 'ok'}


@app.get('/api/dashboard')
def dashboard() -> dict[str, Any]:
    return STATE.snapshot()


@app.post('/api/control/start')
def control_start() -> dict[str, Any]:
    dashboard_data = STATE.start()
    return control_response('start', '시작 버튼: mock 자동매매 루프를 시작했습니다.', dashboard_data)


@app.post('/api/control/pause')
def control_pause() -> dict[str, Any]:
    dashboard_data = STATE.pause()
    return control_response('pause', '일시정지 버튼: mock 자동매매 루프를 멈췄습니다.', dashboard_data)


@app.post('/api/control/run-once')
def control_run_once() -> dict[str, Any]:
    dashboard_data = STATE.run_once()
    return control_response('run-once', '1회 실행 버튼: yfinance 조회와 mock 전략 판단을 실행했습니다.', dashboard_data)


@app.post('/api/control/refresh')
def control_refresh() -> dict[str, Any]:
    dashboard_data = STATE.refresh()
    return control_response('refresh', '새로고침 버튼: position/trade_log를 다시 읽었습니다.', dashboard_data)


@app.post('/api/control/close')
def control_close() -> dict[str, Any]:
    dashboard_data = STATE.close()
    return control_response('close', '종료 버튼: mock 자동매매 루프를 종료 상태로 변경했습니다.', dashboard_data)
