import csv
from datetime import datetime
from typing import Any

from security import TRADE_LOG_FILE, ensure_data_dir


CSV_ENCODING = "utf-8-sig"

TRADE_LOG_FIELDS = [
    "time",
    "action",
    "reason",
    "price",
    "quantity",
    "amount",
    "avg_price",
    "invested_amount",
    "profit_pct",
    "step",
    "raw_unit_amount",
    "adjusted_unit_amount",
    "unit_shares",
]


def ensure_trade_log() -> None:
    """CSV 로그 파일이 없거나 헤더가 다르면 새 형식으로 초기화한다."""
    ensure_data_dir()

    if TRADE_LOG_FILE.exists():
        first_line = TRADE_LOG_FILE.read_text(encoding=CSV_ENCODING).splitlines()
        if first_line and first_line[0] == ",".join(TRADE_LOG_FIELDS):
            return

    with TRADE_LOG_FILE.open("w", newline="", encoding=CSV_ENCODING) as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_LOG_FIELDS)
        writer.writeheader()


def log_trade(
    *,
    action: str,
    reason: str,
    price: float,
    quantity: float,
    amount: float,
    avg_price: float,
    invested_amount: float,
    profit_pct: float,
    step: int,
    raw_unit_amount: float,
    adjusted_unit_amount: float,
    unit_shares: float,
) -> None:
    """매수와 매도 체결 결과를 CSV에 누적 기록한다."""
    ensure_trade_log()

    row: dict[str, Any] = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "action": action,
        "reason": reason,
        "price": round(price, 6),
        "quantity": round(quantity, 10),
        "amount": round(amount, 2),
        "avg_price": round(avg_price, 6),
        "invested_amount": round(invested_amount, 2),
        "profit_pct": round(profit_pct, 4),
        "step": step,
        "raw_unit_amount": round(raw_unit_amount, 2),
        "adjusted_unit_amount": round(adjusted_unit_amount, 2),
        "unit_shares": round(unit_shares, 10),
    }

    with TRADE_LOG_FILE.open("a", newline="", encoding=CSV_ENCODING) as file:
        writer = csv.DictWriter(file, fieldnames=TRADE_LOG_FIELDS)
        writer.writerow(row)


def log_error(message: str) -> None:
    """프로그램을 종료하지 않고 오류를 콘솔에 남긴다."""
    print(f"[ERROR {datetime.now().isoformat(timespec='seconds')}] {message}")
