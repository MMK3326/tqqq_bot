"""매매 실행 엔진.

run_position_cycle: 단일 종목 1사이클 (시그널 → 안전장치 → 주문 → 상태 갱신)
run_cycle:         활성 종목 전체 사이클 + 일일 손실 한도 평가 + equity 기록

안전장치(safety 모듈)는 시그널 생성 후, 주문 직전에 적용된다. 즉:
- HOLD 시그널은 항상 그대로 기록된다.
- BUY/SELL 시그널은 다음 게이트를 통과해야 broker.place_order로 전달된다:
  1) 전역 kill switch (run_cycle에서 미리 평가, allow_orders 플래그로 전파)
  2) 장 시간 (MARKET_HOURS_STRICT=true일 때만)
  3) 주문 멱등성 (직전 동일 action이 윈도우 안에 있으면 차단)
"""

from typing import Any

from . import db, safety
from .broker import Broker, OrderFill
from .strategies import Signal, StrategyContext, get_strategy


def empty_state() -> dict[str, Any]:
    return {
        'quantity': 0.0,
        'avg_price': 0.0,
        'first_price': 0.0,
        'invested_amount': 0.0,
        'bought_steps': [],
        'cycle_count': 0,
    }


def _apply_buy(state: dict[str, Any], fill: OrderFill, signal: Signal) -> dict[str, Any]:
    old_qty = float(state.get('quantity', 0.0))
    old_invested = float(state.get('invested_amount', 0.0))
    new_qty = old_qty + fill.quantity
    new_invested = old_invested + fill.amount

    steps = {int(s) for s in state.get('bought_steps', [])}
    step = int(signal.extra.get('step', 0))
    if step > 0:
        steps.add(step)

    return {
        **state,
        'quantity': new_qty,
        'avg_price': (new_invested / new_qty) if new_qty > 0 else 0.0,
        'first_price': float(state.get('first_price') or fill.price),
        'invested_amount': new_invested,
        'bought_steps': sorted(steps),
        'cycle_count': int(state.get('cycle_count', 0)),
    }


def _apply_sell(state: dict[str, Any], fill: OrderFill) -> dict[str, Any]:
    """익절 전량 매도 후 새 사이클로 리셋. 직전 체결가를 새 first_price로 사용."""
    cycle_count = int(state.get('cycle_count', 0)) + 1
    new_state = empty_state()
    new_state['cycle_count'] = cycle_count
    new_state['first_price'] = float(fill.price)
    return new_state


def run_position_cycle(broker: Broker, position: dict[str, Any],
                       *, allow_orders: bool = True,
                       block_reason: str | None = None) -> dict[str, Any]:
    """단일 종목 1사이클 실행: 시장 데이터 → 전략 → (선택) 주문 → 상태 갱신.

    - allow_orders=False: 시그널은 생성/기록하되 주문은 실행하지 않는다 (run_cycle에서
      kill switch가 활성이거나 일일 손실 한도에 도달했을 때 전파).
    - block_reason: allow_orders=False일 때 result['blocked']에 기록될 사유.
    """
    pos_id = int(position['id'])
    strategy = get_strategy(position['strategy'], position['params'])
    market_data = broker.get_market_data(position['ticker'], position['market'])

    state = position.get('state') or empty_state()
    invested = float(state.get('invested_amount', 0.0))
    budget = float(position['budget'])
    context = StrategyContext(
        state=state,
        budget=budget,
        cash_balance=max(0.0, budget - invested),
    )

    signal = strategy.generate_signal(market_data, context)
    db.log_signal(
        position_id=pos_id,
        action=signal.action,
        reason=signal.reason,
        price=float(market_data.last_price),
    )

    result: dict[str, Any] = {
        'position_id': pos_id,
        'ticker': position['ticker'],
        'market': position['market'],
        'current_price': market_data.last_price,
        'signal': {
            'action': signal.action,
            'reason': signal.reason,
            'amount': signal.amount,
            'quantity': signal.quantity,
            **signal.extra,
        },
        'state_before': state,
        'state_after': state,
        'order': None,
        'blocked': None,
    }

    if signal.action == 'HOLD':
        return result

    # 전역 차단 (kill switch / 일일 손실 한도)
    if not allow_orders:
        result['blocked'] = block_reason or '전역 차단'
        return result

    # 장 시간 차단
    market_gate = safety.check_market_hours(position['market'])
    if not market_gate.allowed:
        result['blocked'] = market_gate.reason
        return result

    # 멱등성 차단
    idem_gate = safety.check_idempotency(pos_id, signal.action)
    if not idem_gate.allowed:
        result['blocked'] = idem_gate.reason
        return result

    if signal.action == 'BUY':
        amount = float(signal.amount or 0.0)
        if amount <= 0 or market_data.last_price <= 0:
            return result
        qty = amount / float(market_data.last_price)
        fill = broker.place_order(
            position['ticker'], position['market'], 'BUY', qty,
            price=float(market_data.last_price),
        )
        new_state = _apply_buy(state, fill, signal)
    else:  # SELL
        qty = float(signal.quantity or state.get('quantity', 0.0))
        if qty <= 0:
            return result
        fill = broker.place_order(
            position['ticker'], position['market'], 'SELL', qty,
            price=float(market_data.last_price),
        )
        new_state = _apply_sell(state, fill)

    db.update_position_state(pos_id, new_state)
    order_id = db.log_order(
        position_id=pos_id,
        action=fill.action,
        reason=signal.reason,
        price=fill.price,
        quantity=fill.quantity,
        amount=fill.amount,
        avg_price=float(new_state.get('avg_price', 0.0)),
        invested_amount=float(new_state.get('invested_amount', 0.0)),
        profit_pct=float(signal.extra.get('profit_pct', 0.0)),
        step=int(signal.extra.get('step', 0)),
        raw_unit_amount=float(signal.extra.get('raw_unit_amount', 0.0)),
        adjusted_unit_amount=float(signal.extra.get('adjusted_unit_amount', 0.0)),
        unit_shares=float(signal.extra.get('unit_shares', 0.0)),
    )

    result['state_after'] = new_state
    result['order'] = {
        'id': order_id,
        'action': fill.action,
        'price': fill.price,
        'quantity': fill.quantity,
        'amount': fill.amount,
        'avg_price': float(new_state.get('avg_price', 0.0)),
        'invested_amount': float(new_state.get('invested_amount', 0.0)),
        'ts': fill.ts,
    }
    return result


def run_cycle(broker: Broker) -> list[dict[str, Any]]:
    """활성 종목 전체에 대해 1사이클 실행.

    사이클 시작 시:
    - 전역 kill switch가 active면 모든 종목에 대해 주문 차단(시그널은 그대로 기록)
    - 그렇지 않으면 일일 손실 한도 점검 → 도달 시 kill switch 자동 트립

    각 종목 실행은 try/except로 격리. 사이클 마지막에 equity_snapshot 기록.
    """
    positions = db.list_positions(enabled_only=True)

    block_reason: str | None = None
    if safety.is_kill_switch_active():
        ks = safety.kill_switch_status()
        block_reason = f"전역 kill switch 활성: {ks['reason']}" if ks['reason'] else '전역 kill switch 활성'
    else:
        daily = safety.check_daily_loss_limit(broker, positions)
        if not daily.allowed:
            block_reason = daily.reason

    allow_orders = block_reason is None
    results: list[dict[str, Any]] = []
    for pos in positions:
        try:
            results.append(run_position_cycle(
                broker, pos,
                allow_orders=allow_orders,
                block_reason=block_reason,
            ))
        except Exception as exc:
            results.append({
                'position_id': pos['id'],
                'ticker': pos['ticker'],
                'error': str(exc),
            })

    # equity 기록 (사이클 후 상태 기준, 시세 조회 실패는 무시)
    try:
        snap = safety.portfolio_value(broker, db.list_positions(enabled_only=True))
        db.record_equity_snapshot(
            total_asset=snap['total'],
            cash=snap['cash_equivalent'],
            invested=snap['invested'],
        )
    except Exception:
        pass

    return results
