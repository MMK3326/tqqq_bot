from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
POSITION_FILE = DATA_DIR / "position.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.csv"
YFINANCE_CACHE_DIR = Path.home() / ".tqqq_bot_yfinance_cache"


def ensure_data_dir() -> None:
    """data 폴더가 없으면 자동으로 생성한다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def mask_secret(value: str, visible: int = 4) -> str:
    """나중에 API 키를 출력해야 할 때 일부만 보이도록 가린다."""
    if not value:
        return ""
    if len(value) <= visible:
        return "*" * len(value)
    return f"{value[:visible]}{'*' * (len(value) - visible)}"
