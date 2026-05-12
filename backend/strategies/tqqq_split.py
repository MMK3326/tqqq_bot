"""TQQQ 1단계 분할매수/익절 전략.

기존 strategy/tqqq_strategy.py 로직을 Strategy 플러그인 형태로 이식한 것.

운용 규칙:
- 신규 사이클은 보유 0일 때 시작한다. 현재가를 first_price로 잡고 1분할(0단계) 매수.
- 최초가 대비 -drop_interval_pct % 떨어질 때마다 N분할 추가매수(N=현재 도달 단계).
  과거 단계는 소급하지 않는다.
- 평단가 대비 +take_profit_pct % 도달 시 전량 매도하고 사이클 종료, 직전 체결가를
  새 사이클의 first_price로 사용한다.
- budget(예산) 안에서만 매수한다. use_integer_share_unit=True면 1분할 금액을 정수 주 단위로 보정.
"""

from math import floor
from typing import Any

from .base import Signal, Strategy, StrategyContext


class TQQQSplitStrategy(Strategy):
    name = 'tqqq_split'
    display_name = 'TQQQ 분할매수/익절'
    supported_markets = ['US']
    params_schema = {
        'base_split_count':       {'type': 'int',   'default': 40,   'label': '분할 횟수',         'min': 1,   'max': 200},
        'drop_interval_pct':      {'type': 'float', 'default': 0.5,  'label': '추가매수 간격(%)', 'min': 0.1, 'max': 10.0},
        'take_profit_pct':        {'type': 'float', 'default': 0.5,  'label': '익절 기준(%)',     'min': 0.1, 'max': 50.0},
        'use_integer_share_unit': {'type': 'bool',  'default': True, 'label': '정수 주 단위 보정'},
    }

    def _calc_unit(self, current_price: float, budget: float) -> dict[str, float]:
        split_count = max(1, int(self.params['base_split_count']))
        raw_unit = budget / split_count
        if self.params['use_integer_share_unit']:
            shares = max(1, floor(raw_unit / current_price)) if current_price > 0 else 1
            adjusted = shares * current_price
        else:
            adjusted = raw_unit
            shares = (raw_unit / current_price) if current_price > 0 else 0.0
        return {
            'raw_unit_amount': raw_unit,
            'adjusted_unit_amount': adjusted,
            'unit_shares': float(shares),
        }

    def _cap_amount(self, desired: float, current_price: float,
                    remaining_investable: float, cash_balance: float) -> float:
        capped = min(desired, remaining_investable, cash_balance)
        if not self.params['use_integer_share_unit']:
            return max(0.0, capped)
        if current_price <= 0:
            return 0.0
        shares = floor(capped / current_price)
        if shares <= 0:
            return 0.0
        return shares * current_price

    def generate_signal(self, market_data, context: StrategyContext) -> Signal:
        current_price = float(market_data.last_price)
        state: dict[str, Any] = context.state or {}
        budget = float(context.budget)
        cash_balance = float(context.cash_balance)

        quantity = float(state.get('quantity', 0.0))
        avg_price = float(state.get('avg_price', 0.0))
        first_price = float(state.get('first_price', 0.0))
        invested = float(state.get('invested_amount', 0.0))
        bought_steps = {int(s) for s in state.get('bought_steps', [])}

        drop_interval_pct = float(self.params['drop_interval_pct'])
        take_profit_pct = float(self.params['take_profit_pct'])

        unit = self._calc_unit(current_price, budget)
        remaining = max(0.0, budget - invested)

        # 대시보드 표시에 쓰일 메타데이터
        current_step = 0
        next_buy_price = 0.0
        if first_price > 0:
            drop_pct = max(0.0, (first_price - current_price) / first_price * 100)
            current_step = int(floor(drop_pct / drop_interval_pct))
            next_step = (max(bought_steps) + 1) if bought_steps else 1
            next_buy_price = first_price * (1 - (drop_interval_pct * next_step) / 100)
        next_tp_price = avg_price * (1 + take_profit_pct / 100) if avg_price > 0 else 0.0
        profit_pct = ((current_price - avg_price) / avg_price * 100) if (quantity > 0 and avg_price > 0) else 0.0

        extra: dict[str, Any] = {
            'raw_unit_amount': unit['raw_unit_amount'],
            'adjusted_unit_amount': unit['adjusted_unit_amount'],
            'unit_shares': unit['unit_shares'],
            'max_invest_amount': budget,
            'remaining_investable': remaining,
            'invested_ratio_pct': (invested / budget * 100) if budget else 0.0,
            'profit_pct': profit_pct,
            'current_step': current_step,
            'next_buy_price': next_buy_price,
            'next_take_profit_price': next_tp_price,
            'step': 0,
        }

        if current_price <= 0:
            return Signal(action='HOLD', reason='현재가가 0 이하입니다.', extra=extra)
        if cash_balance <= 0:
            return Signal(action='HOLD', reason='현금 잔고가 없습니다.', extra=extra)

        # 신규 사이클: 보유 0이면 1분할(0단계) 매수
        if quantity <= 0:
            amount = self._cap_amount(unit['adjusted_unit_amount'], current_price, budget, cash_balance)
            if amount <= 0:
                return Signal(action='HOLD', reason='최초 매수 가능 금액이 없습니다.', extra=extra)
            return Signal(action='BUY', amount=amount,
                          reason='새 사이클 최초 1분할 매수',
                          extra={**extra, 'step': 0})

        # 평단 대비 +take_profit_pct% 도달 시 전량 매도
        if avg_price > 0 and current_price >= avg_price * (1 + take_profit_pct / 100):
            return Signal(action='SELL', quantity=quantity,
                          reason=f'평단가 대비 +{take_profit_pct}% 익절',
                          extra={**extra, 'step': current_step})

        if first_price <= 0:
            return Signal(action='HOLD',
                          reason='최초 기준가가 없어 추가매수를 판단할 수 없습니다.',
                          extra=extra)

        drop_pct = max(0.0, (first_price - current_price) / first_price * 100)
        step = int(floor(drop_pct / drop_interval_pct))
        if step <= 0:
            return Signal(action='HOLD', reason='추가매수 구간 전입니다.', extra={**extra, 'step': 0})

        max_bought_step = max(bought_steps) if bought_steps else 0
        if step <= max_bought_step:
            return Signal(action='HOLD',
                          reason=f'{step}단계는 이미 지나간 구간이라 소급 매수하지 않습니다.',
                          extra={**extra, 'step': step})

        if remaining <= 0:
            return Signal(action='HOLD', reason='할당 예산 한도에 도달했습니다.',
                          extra={**extra, 'step': step})

        amount = self._cap_amount(unit['adjusted_unit_amount'] * step,
                                  current_price, remaining, cash_balance)
        if amount <= 0:
            return Signal(action='HOLD', reason='추가매수 가능 금액이 없습니다.',
                          extra={**extra, 'step': step})
        return Signal(action='BUY', amount=amount,
                      reason=f'최초가 대비 -{drop_interval_pct * step:.1f}% 도달, {step}분할 추가매수',
                      extra={**extra, 'step': step})
