from math import floor
from typing import Any


def calculate_unit(
    *,
    current_price: float,
    total_capital: float,
    max_invest_ratio: float,
    base_split_count: int,
    use_integer_share_unit: bool,
) -> dict[str, float]:
    """
    1분할 금액을 계산한다.

    USE_INTEGER_SHARE_UNIT=True이면 현재가 기준 정수 주식 수량으로 보정한다.
    이 계산은 주문 실행이 아니라 전략 판단에 필요한 숫자 계산만 담당한다.
    """
    max_invest_amount = total_capital * max_invest_ratio
    raw_unit_amount = max_invest_amount / base_split_count

    if use_integer_share_unit:
        adjusted_unit_shares = max(1, floor(raw_unit_amount / current_price))
        adjusted_unit_amount = adjusted_unit_shares * current_price
    else:
        adjusted_unit_amount = raw_unit_amount
        adjusted_unit_shares = raw_unit_amount / current_price

    return {
        "raw_unit_amount": raw_unit_amount,
        "adjusted_unit_amount": adjusted_unit_amount,
        "unit_shares": float(adjusted_unit_shares),
    }


def calculate_metrics(
    *,
    current_price: float,
    position: dict[str, Any],
    total_capital: float,
    max_invest_ratio: float,
    base_split_count: int,
    drop_interval_pct: float,
    take_profit_pct: float,
    use_integer_share_unit: bool,
) -> dict[str, Any]:
    """콘솔 UI와 주문 판단에 필요한 모든 전략 지표를 계산한다."""
    quantity = float(position.get("quantity", 0.0))
    avg_price = float(position.get("avg_price", 0.0))
    first_price = float(position.get("first_price", 0.0))
    invested_amount = float(position.get("invested_amount", 0.0))
    bought_steps = [int(step) for step in position.get("bought_steps", [])]

    unit = calculate_unit(
        current_price=current_price,
        total_capital=total_capital,
        max_invest_ratio=max_invest_ratio,
        base_split_count=base_split_count,
        use_integer_share_unit=use_integer_share_unit,
    )

    max_invest_amount = total_capital * max_invest_ratio
    remaining_investable = max(0.0, max_invest_amount - invested_amount)
    invested_ratio_pct = invested_amount / total_capital * 100 if total_capital else 0.0
    profit_pct = (current_price - avg_price) / avg_price * 100 if quantity > 0 and avg_price > 0 else 0.0

    current_step = 0
    next_buy_price = 0.0
    if first_price > 0:
        drop_pct = max(0.0, (first_price - current_price) / first_price * 100)
        current_step = floor(drop_pct / drop_interval_pct)

        # 과거 구간은 소급하지 않으므로 가장 높은 매수 완료 단계 다음 가격만 표시한다.
        next_step = (max(bought_steps) + 1) if bought_steps else 1
        next_buy_price = first_price * (1 - (drop_interval_pct * next_step) / 100)

    next_take_profit_price = avg_price * (1 + take_profit_pct / 100) if avg_price > 0 else 0.0

    return {
        **unit,
        "max_invest_amount": max_invest_amount,
        "remaining_investable": remaining_investable,
        "invested_ratio_pct": invested_ratio_pct,
        "profit_pct": profit_pct,
        "current_step": int(current_step),
        "next_buy_price": next_buy_price,
        "next_take_profit_price": next_take_profit_price,
    }


def _cap_order_amount(
    *,
    desired_amount: float,
    current_price: float,
    remaining_investable: float,
    cash_balance: float,
    use_integer_share_unit: bool,
) -> float:
    """운용 한도와 현금 잔고 안에서 실제 주문 금액을 보정한다."""
    capped_amount = min(desired_amount, remaining_investable, cash_balance)

    if not use_integer_share_unit:
        return max(0.0, capped_amount)

    # 정수 주 옵션에서는 1주 미만 금액으로 주문하지 않는다.
    affordable_shares = floor(capped_amount / current_price)
    if affordable_shares <= 0:
        return 0.0
    return affordable_shares * current_price


def generate_signal(
    *,
    current_price: float,
    cash_balance: float,
    position: dict[str, Any],
    total_capital: float,
    max_invest_ratio: float,
    base_split_count: int,
    drop_interval_pct: float,
    take_profit_pct: float,
    use_integer_share_unit: bool,
) -> dict[str, Any]:
    """
    TQQQ 전략 신호를 만든다.

    이 함수는 broker 종류를 알지 못하고, 실제 주문도 실행하지 않는다.
    BUY, SELL, HOLD 중 하나와 주문에 필요한 계산값만 반환한다.
    """
    quantity = float(position.get("quantity", 0.0))
    avg_price = float(position.get("avg_price", 0.0))
    first_price = float(position.get("first_price", 0.0))
    invested_amount = float(position.get("invested_amount", 0.0))
    bought_steps = set(int(step) for step in position.get("bought_steps", []))

    metrics = calculate_metrics(
        current_price=current_price,
        position=position,
        total_capital=total_capital,
        max_invest_ratio=max_invest_ratio,
        base_split_count=base_split_count,
        drop_interval_pct=drop_interval_pct,
        take_profit_pct=take_profit_pct,
        use_integer_share_unit=use_integer_share_unit,
    )

    max_invest_amount = metrics["max_invest_amount"]
    remaining_investable = metrics["remaining_investable"]
    unit_amount = metrics["adjusted_unit_amount"]

    base_signal = {
        **metrics,
        "action": "HOLD",
        "reason": "매매 조건 없음",
        "amount": 0.0,
        "quantity": 0.0,
        "step": 0,
    }

    if current_price <= 0:
        return {**base_signal, "reason": "현재가가 0 이하입니다."}

    if cash_balance <= 0:
        return {**base_signal, "reason": "현금 잔고가 없습니다."}

    # 포지션이 없으면 현재가를 새 최초 기준가로 삼고 즉시 1분할 매수한다.
    if quantity <= 0:
        amount = _cap_order_amount(
            desired_amount=unit_amount,
            current_price=current_price,
            remaining_investable=max_invest_amount,
            cash_balance=cash_balance,
            use_integer_share_unit=use_integer_share_unit,
        )
        if amount <= 0:
            return {**base_signal, "reason": "최초 매수 가능 금액이 없습니다."}
        return {
            **base_signal,
            "action": "BUY",
            "reason": "새 사이클 최초 1분할 매수",
            "amount": amount,
            "step": 0,
        }

    # 평단가 대비 +TAKE_PROFIT_PCT 도달 시 전량 매도한다.
    if avg_price > 0 and current_price >= avg_price * (1 + take_profit_pct / 100):
        return {
            **base_signal,
            "action": "SELL",
            "reason": f"평단가 대비 +{take_profit_pct}% 익절",
            "quantity": quantity,
            "step": metrics["current_step"],
        }

    if first_price <= 0:
        return {**base_signal, "reason": "최초 기준가가 없어 추가매수를 판단할 수 없습니다."}

    drop_pct = max(0.0, (first_price - current_price) / first_price * 100)
    step = floor(drop_pct / drop_interval_pct)

    if step <= 0:
        return {**base_signal, "reason": "추가매수 구간 전입니다."}

    max_bought_step = max(bought_steps) if bought_steps else 0
    if step <= max_bought_step:
        return {
            **base_signal,
            "reason": f"{step}단계는 이미 지나간 구간이라 소급 매수하지 않습니다.",
            "step": step,
        }

    if remaining_investable <= 0:
        return {**base_signal, "reason": "최대 운용 가능 금액에 도달했습니다.", "step": step}

    # 과거 구간을 소급 매수하지 않고, 현재 도달한 단계 수만큼만 이번 주문 금액을 만든다.
    amount = _cap_order_amount(
        desired_amount=unit_amount * step,
        current_price=current_price,
        remaining_investable=remaining_investable,
        cash_balance=cash_balance,
        use_integer_share_unit=use_integer_share_unit,
    )
    if amount <= 0:
        return {**base_signal, "reason": "추가매수 가능 금액이 없습니다.", "step": step}

    return {
        **base_signal,
        "action": "BUY",
        "reason": f"최초가 대비 -{drop_interval_pct * step:.1f}% 도달, {step}분할 추가매수",
        "amount": amount,
        "step": step,
    }
