import csv
import json
from typing import Any

import yfinance as yf

import config
from security import POSITION_FILE, TRADE_LOG_FILE, YFINANCE_CACHE_DIR, ensure_data_dir


# yfinance의 기본 캐시 위치가 Windows 환경에서 권한 문제를 낼 수 있어 별도 위치를 사용한다.
ensure_data_dir()
yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))


_LAST_PRICE: dict[str, float] = {}


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _empty_position(symbol: str = config.SYMBOL, cycle_count: int = 0) -> dict[str, Any]:
    """position.json의 기본 구조를 만든다."""
    return {
        "symbol": symbol,
        "quantity": 0.0,
        "avg_price": 0.0,
        "first_price": 0.0,
        "invested_amount": 0.0,
        "bought_steps": [],
        "cycle_count": cycle_count,
    }


def _load_position() -> dict[str, Any]:
    """파일이 없거나 형식이 다르면 새 구조로 자동 생성한다."""
    ensure_data_dir()

    if not POSITION_FILE.exists():
        position = _empty_position()
        _save_position(position)
        return position

    try:
        with POSITION_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        data = _empty_position()
        _save_position(data)
        return data

    # 이전 버전의 {"cash": ..., "positions": ...} 구조가 있으면 새 구조로 변환한다.
    if "positions" in data:
        old_position = data.get("positions", {}).get(config.SYMBOL, {})
        data = {
            "symbol": config.SYMBOL,
            "quantity": float(old_position.get("quantity", 0.0)),
            "avg_price": float(old_position.get("avg_price", 0.0)),
            "first_price": float(old_position.get("reference_price", 0.0)),
            "invested_amount": float(old_position.get("invested_amount", 0.0)),
            "bought_steps": list(old_position.get("bought_drop_steps", [])),
            "cycle_count": 0,
        }
        _save_position(data)
        return data

    position = _empty_position(symbol=data.get("symbol", config.SYMBOL), cycle_count=int(data.get("cycle_count", 0)))
    position.update(
        {
            "quantity": float(data.get("quantity", 0.0)),
            "avg_price": float(data.get("avg_price", 0.0)),
            "first_price": float(data.get("first_price", 0.0)),
            "invested_amount": float(data.get("invested_amount", 0.0)),
            "bought_steps": [int(step) for step in data.get("bought_steps", [])],
        }
    )
    return position


def _save_position(position: dict[str, Any]) -> None:
    """모의 포지션 상태를 position.json에 저장한다."""
    ensure_data_dir()
    with POSITION_FILE.open("w", encoding="utf-8") as file:
        json.dump(position, file, indent=2, ensure_ascii=False)


def set_current_price(symbol: str, price: float) -> None:
    """main.py에서 조회한 현재가를 주문 체결가로 재사용한다."""
    if price <= 0:
        raise ValueError("현재가는 0보다 커야 합니다.")
    _LAST_PRICE[symbol] = float(price)


def get_current_price(symbol: str) -> float:
    """
    yfinance로 현재가를 조회한다.

    네트워크 오류가 발생하면 이전에 성공한 가격을 유지한다.
    이전 가격도 없으면 예외를 올리고, main.py가 종료하지 않고 다음 루프에서 재시도한다.
    """
    try:
        ticker = yf.Ticker(symbol)
        price = ticker.fast_info.get("last_price")

        if price is None:
            history = ticker.history(period="1d", interval="1m")
            if history.empty:
                raise RuntimeError("yfinance 가격 응답이 비어 있습니다.")
            price = history["Close"].dropna().iloc[-1]

        price = float(price)
        if price <= 0:
            raise RuntimeError("yfinance 가격이 0 이하입니다.")

        _LAST_PRICE[symbol] = price
        return price
    except Exception as exc:
        if symbol in _LAST_PRICE:
            print(f"[가격 조회 오류] 이전 가격 유지: {exc}")
            return _LAST_PRICE[symbol]
        raise RuntimeError(f"{symbol} 현재가 조회 실패: {exc}") from exc


def _get_order_price(symbol: str) -> float:
    """한 루프 안에서 조회한 현재가를 주문 체결가로 사용한다."""
    if symbol in _LAST_PRICE:
        return _LAST_PRICE[symbol]
    return get_current_price(symbol)


def get_cash_balance() -> float:
    """모의 현금 잔고를 계산한다. 현금은 별도 저장하지 않고 투입금 기준으로 계산한다."""
    position = _load_position()
    fallback = max(0.0, config.TOTAL_CAPITAL - float(position.get("invested_amount", 0.0)))

    if not TRADE_LOG_FILE.exists():
        return fallback

    try:
        with TRADE_LOG_FILE.open("r", newline="", encoding="utf-8-sig") as file:
            rows = list(csv.DictReader(file))
    except OSError:
        return fallback

    realized = 0.0
    for row in rows:
        if row.get("action") == "SELL":
            realized += _to_float(row.get("amount")) - _to_float(row.get("quantity")) * _to_float(row.get("avg_price"))

    return max(0.0, config.TOTAL_CAPITAL + realized - float(position.get("invested_amount", 0.0)))


def get_position(symbol: str) -> dict[str, Any]:
    """현재 포지션을 strategy에 넘길 공통 dict 형태로 반환한다."""
    position = _load_position()
    if position.get("symbol") != symbol:
        position["symbol"] = symbol
        _save_position(position)
    return position


def buy_market(symbol: str, amount: float) -> dict[str, Any]:
    """실제 주문 없이 position.json만 업데이트하는 모의 시장가 매수."""
    if amount <= 0:
        raise ValueError("매수 금액은 0보다 커야 합니다.")

    price = _get_order_price(symbol)
    position = _load_position()
    cash_balance = get_cash_balance()
    order_amount = min(float(amount), cash_balance)

    if order_amount <= 0:
        raise ValueError("매수 가능한 현금이 없습니다.")

    quantity = order_amount / price
    old_quantity = float(position.get("quantity", 0.0))
    old_invested = float(position.get("invested_amount", 0.0))
    new_quantity = old_quantity + quantity
    new_invested = old_invested + order_amount

    position["symbol"] = symbol
    position["quantity"] = new_quantity
    position["avg_price"] = new_invested / new_quantity
    position["first_price"] = float(position.get("first_price") or price)
    position["invested_amount"] = new_invested
    position["bought_steps"] = sorted(set(int(step) for step in position.get("bought_steps", [])))
    _save_position(position)

    return {
        "symbol": symbol,
        "action": "BUY",
        "price": price,
        "quantity": quantity,
        "amount": order_amount,
        "avg_price": position["avg_price"],
        "invested_amount": position["invested_amount"],
    }


def sell_market(symbol: str, quantity: float) -> dict[str, Any]:
    """실제 주문 없이 position.json만 업데이트하는 모의 시장가 매도."""
    if quantity <= 0:
        raise ValueError("매도 수량은 0보다 커야 합니다.")

    price = _get_order_price(symbol)
    position = _load_position()
    held_quantity = float(position.get("quantity", 0.0))

    if held_quantity <= 0:
        raise ValueError(f"{symbol} 보유 수량이 없습니다.")

    sell_quantity = min(float(quantity), held_quantity)
    amount = sell_quantity * price
    avg_price = float(position.get("avg_price", 0.0))

    # 이 전략은 익절 시 전량 매도만 사용한다. 전량 매도 후 새 사이클 기준가를 현재가로 설정한다.
    cycle_count = int(position.get("cycle_count", 0)) + 1
    new_position = _empty_position(symbol=symbol, cycle_count=cycle_count)
    new_position["first_price"] = price
    _save_position(new_position)

    return {
        "symbol": symbol,
        "action": "SELL",
        "price": price,
        "quantity": sell_quantity,
        "amount": amount,
        "avg_price": avg_price,
        "invested_amount": 0.0,
    }


def mark_step_bought(symbol: str, step: int) -> None:
    """같은 추가매수 단계를 중복 매수하지 않도록 저장한다."""
    if step <= 0:
        return

    position = _load_position()
    position["symbol"] = symbol
    bought_steps = set(int(item) for item in position.get("bought_steps", []))
    bought_steps.add(int(step))
    position["bought_steps"] = sorted(bought_steps)
    _save_position(position)
