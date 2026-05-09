import os
import time
from typing import Any

import config
from security import ensure_data_dir
from strategy.tqqq_strategy import calculate_metrics, generate_signal
from utils.logger import ensure_trade_log, log_error, log_trade


def select_broker():
    """config.MODE 값에 따라 사용할 broker 모듈을 선택한다."""
    if config.MODE == "mock":
        from broker import mock_broker as broker

        return broker

    if config.MODE == "real":
        from broker import kis_broker as broker

        return broker

    raise ValueError('config.MODE는 "mock" 또는 "real"이어야 합니다.')


def run_once(broker) -> dict[str, Any]:
    """현재가 조회부터 주문, 로그 기록까지 한 사이클을 실행한다."""
    symbol = config.SYMBOL
    current_price = broker.get_current_price(symbol)

    # broker 주문 함수가 같은 현재가를 체결가로 쓰도록 전달한다.
    if hasattr(broker, "set_current_price"):
        broker.set_current_price(symbol, current_price)

    cash_balance = broker.get_cash_balance()
    position = broker.get_position(symbol)

    signal = generate_signal(
        current_price=current_price,
        cash_balance=cash_balance,
        position=position,
        total_capital=config.TOTAL_CAPITAL,
        max_invest_ratio=config.MAX_INVEST_RATIO,
        base_split_count=config.BASE_SPLIT_COUNT,
        drop_interval_pct=config.DROP_INTERVAL_PCT,
        take_profit_pct=config.TAKE_PROFIT_PCT,
        use_integer_share_unit=config.USE_INTEGER_SHARE_UNIT,
    )

    action = signal["action"]
    order_result: dict[str, Any] | None = None

    if action == "BUY":
        order_result = broker.buy_market(symbol, signal["amount"])
        if hasattr(broker, "mark_step_bought"):
            broker.mark_step_bought(symbol, int(signal["step"]))
    elif action == "SELL":
        order_result = broker.sell_market(symbol, signal["quantity"])

    if order_result is not None:
        log_trade(
            action=order_result["action"],
            reason=signal["reason"],
            price=order_result["price"],
            quantity=order_result["quantity"],
            amount=order_result["amount"],
            avg_price=order_result["avg_price"],
            invested_amount=order_result["invested_amount"],
            profit_pct=signal["profit_pct"],
            step=int(signal["step"]),
            raw_unit_amount=signal["raw_unit_amount"],
            adjusted_unit_amount=signal["adjusted_unit_amount"],
            unit_shares=signal["unit_shares"],
        )

    latest_position = broker.get_position(symbol)
    latest_metrics = calculate_metrics(
        current_price=current_price,
        position=latest_position,
        total_capital=config.TOTAL_CAPITAL,
        max_invest_ratio=config.MAX_INVEST_RATIO,
        base_split_count=config.BASE_SPLIT_COUNT,
        drop_interval_pct=config.DROP_INTERVAL_PCT,
        take_profit_pct=config.TAKE_PROFIT_PCT,
        use_integer_share_unit=config.USE_INTEGER_SHARE_UNIT,
    )

    return {
        "current_price": current_price,
        "position": latest_position,
        "metrics": latest_metrics,
        "signal": signal,
        "order_result": order_result,
    }


def format_money(value: float) -> str:
    """달러 표시용 포맷."""
    return f"${value:,.2f}"


def print_console_ui(result: dict[str, Any]) -> None:
    """요구사항의 콘솔 UI 항목을 한 화면에 출력한다."""
    current_price = float(result["current_price"])
    position = result["position"]
    metrics = result["metrics"]
    signal = result["signal"]
    order_result = result["order_result"]

    quantity = float(position.get("quantity", 0.0))
    avg_price = float(position.get("avg_price", 0.0))
    first_price = float(position.get("first_price", 0.0))
    invested_amount = float(position.get("invested_amount", 0.0))
    bought_steps = position.get("bought_steps", [])
    cycle_count = int(position.get("cycle_count", 0))

    os.system("cls" if os.name == "nt" else "clear")

    print("TQQQ 1단계 전략 테스트 모의투자")
    print("=" * 56)
    print(f"MODE: {config.MODE} | SYMBOL: {config.SYMBOL} | cycle: {cycle_count}")
    print(f"마지막 신호: {signal['action']} - {signal['reason']}")
    if order_result:
        print(
            "마지막 주문: "
            f"{order_result['action']} {order_result['quantity']:.6f}주 "
            f"@ {format_money(order_result['price'])}"
        )
    print("-" * 56)
    print(f"현재 가격: {format_money(current_price)}")
    print(f"최초 기준가: {format_money(first_price)}")
    print(f"현재 평단가: {format_money(avg_price)}")
    print(f"현재 수익률(%): {metrics['profit_pct']:.4f}%")
    print(f"현재 보유 수량: {quantity:.10f}주")
    print(f"총 투입금: {format_money(invested_amount)}")
    print(f"총 투입률(%): {metrics['invested_ratio_pct']:.4f}%")
    print(f"남은 운용 가능 금액: {format_money(metrics['remaining_investable'])}")
    print(f"다음 추가매수 가격: {format_money(metrics['next_buy_price'])}")
    print(f"다음 익절 가격: {format_money(metrics['next_take_profit_price'])}")
    print(f"현재 매수 단계: {metrics['current_step']}단계 / 매수완료 {bought_steps}")
    print("-" * 56)
    print(f"원래 1분할 금액: {format_money(metrics['raw_unit_amount'])}")
    print(f"보정된 1분할 금액: {format_money(metrics['adjusted_unit_amount'])}")
    print(f"1분할 기준 주식 수량: {metrics['unit_shares']:.10f}주")
    print("=" * 56)
    print(f"{config.STRATEGY_RUN_INTERVAL_SEC}초 후 다시 실행합니다. 종료: Ctrl+C")


def main() -> None:
    """무한 루프 실행 진입점. Ctrl+C 입력 시 안전 종료한다."""
    ensure_data_dir()
    ensure_trade_log()
    broker = select_broker()

    print("TQQQ 자동매매 모의투자 프로그램을 시작합니다. 종료하려면 Ctrl+C를 누르세요.")

    while True:
        try:
            result = run_once(broker)
            print_console_ui(result)
        except KeyboardInterrupt:
            print("\n사용자 요청으로 안전 종료합니다.")
            break
        except Exception as exc:
            log_error(str(exc))

        try:
            time.sleep(config.STRATEGY_RUN_INTERVAL_SEC)
        except KeyboardInterrupt:
            print("\n사용자 요청으로 안전 종료합니다.")
            break


if __name__ == "__main__":
    main()
