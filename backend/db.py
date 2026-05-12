"""SQLite 연결 + 단순 쿼리. stdlib `sqlite3`만 사용 (외부 ORM 의존성 없음)."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from . import config


SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker       TEXT NOT NULL,
    market       TEXT NOT NULL CHECK (market IN ('KR', 'US')),
    name         TEXT,
    strategy     TEXT NOT NULL,
    params       TEXT NOT NULL DEFAULT '{}',
    budget       REAL NOT NULL DEFAULT 0,
    enabled      INTEGER NOT NULL DEFAULT 1,
    state        TEXT NOT NULL DEFAULT '{}',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id           INTEGER NOT NULL,
    ts                    TEXT NOT NULL,
    action                TEXT NOT NULL CHECK (action IN ('BUY','SELL')),
    reason                TEXT,
    price                 REAL,
    quantity              REAL,
    amount                REAL,
    avg_price             REAL,
    invested_amount       REAL,
    profit_pct            REAL,
    step                  INTEGER,
    raw_unit_amount       REAL,
    adjusted_unit_amount  REAL,
    unit_shares           REAL,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);
CREATE INDEX IF NOT EXISTS idx_orders_position_ts ON orders(position_id, ts);

CREATE TABLE IF NOT EXISTS signals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL,
    ts           TEXT NOT NULL,
    action       TEXT NOT NULL,
    reason       TEXT,
    price        REAL,
    FOREIGN KEY (position_id) REFERENCES positions(id)
);
CREATE INDEX IF NOT EXISTS idx_signals_position_ts ON signals(position_id, ts);

CREATE TABLE IF NOT EXISTS equity_snapshots (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    total_asset  REAL,
    cash         REAL,
    invested     REAL
);

CREATE TABLE IF NOT EXISTS system_state (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now().isoformat(timespec='seconds')


def connect() -> sqlite3.Connection:
    config.ensure_data_dir()
    conn = sqlite3.connect(str(config.DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_schema() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


@contextmanager
def cursor() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _row_to_position(row: sqlite3.Row) -> dict[str, Any]:
    return {
        'id': row['id'],
        'ticker': row['ticker'],
        'market': row['market'],
        'name': row['name'],
        'strategy': row['strategy'],
        'params': json.loads(row['params'] or '{}'),
        'budget': float(row['budget']),
        'enabled': bool(row['enabled']),
        'state': json.loads(row['state'] or '{}'),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }


def list_positions(enabled_only: bool = False) -> list[dict[str, Any]]:
    query = 'SELECT * FROM positions'
    if enabled_only:
        query += ' WHERE enabled = 1'
    query += ' ORDER BY id'
    with cursor() as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_position(r) for r in rows]


def get_position(position_id: int) -> dict[str, Any] | None:
    with cursor() as conn:
        row = conn.execute('SELECT * FROM positions WHERE id = ?', (position_id,)).fetchone()
    return _row_to_position(row) if row else None


def get_position_by_ticker(ticker: str) -> dict[str, Any] | None:
    with cursor() as conn:
        row = conn.execute(
            'SELECT * FROM positions WHERE ticker = ? ORDER BY id LIMIT 1',
            (ticker,),
        ).fetchone()
    return _row_to_position(row) if row else None


def insert_position(*, ticker: str, market: str, name: str | None, strategy: str,
                    params: dict[str, Any], budget: float, enabled: bool = True,
                    state: dict[str, Any] | None = None) -> int:
    now = _now()
    with cursor() as conn:
        cur = conn.execute(
            'INSERT INTO positions '
            '(ticker, market, name, strategy, params, budget, enabled, state, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                ticker,
                market,
                name,
                strategy,
                json.dumps(params, ensure_ascii=False),
                float(budget),
                1 if enabled else 0,
                json.dumps(state or {}, ensure_ascii=False),
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


_UPDATABLE_FIELDS = {'ticker', 'market', 'name', 'strategy', 'params', 'budget', 'enabled', 'state'}


def update_position(position_id: int, *, fields: dict[str, Any]) -> None:
    if not fields:
        return
    set_clauses: list[str] = []
    values: list[Any] = []
    for key, val in fields.items():
        if key not in _UPDATABLE_FIELDS:
            raise ValueError(f'Unknown field: {key}')
        if key in ('params', 'state'):
            set_clauses.append(f'{key} = ?')
            values.append(json.dumps(val, ensure_ascii=False))
        elif key == 'enabled':
            set_clauses.append('enabled = ?')
            values.append(1 if val else 0)
        elif key == 'budget':
            set_clauses.append('budget = ?')
            values.append(float(val))
        else:
            set_clauses.append(f'{key} = ?')
            values.append(val)
    set_clauses.append('updated_at = ?')
    values.append(_now())
    values.append(position_id)
    with cursor() as conn:
        conn.execute(
            f'UPDATE positions SET {", ".join(set_clauses)} WHERE id = ?',
            values,
        )


def update_position_state(position_id: int, state: dict[str, Any]) -> None:
    update_position(position_id, fields={'state': state})


def delete_position(position_id: int) -> None:
    with cursor() as conn:
        conn.execute('DELETE FROM orders WHERE position_id = ?', (position_id,))
        conn.execute('DELETE FROM signals WHERE position_id = ?', (position_id,))
        conn.execute('DELETE FROM positions WHERE id = ?', (position_id,))


def log_order(*, position_id: int, action: str, reason: str, price: float,
              quantity: float, amount: float, avg_price: float,
              invested_amount: float, profit_pct: float, step: int,
              raw_unit_amount: float, adjusted_unit_amount: float,
              unit_shares: float) -> int:
    with cursor() as conn:
        cur = conn.execute(
            'INSERT INTO orders '
            '(position_id, ts, action, reason, price, quantity, amount, avg_price, '
            ' invested_amount, profit_pct, step, raw_unit_amount, adjusted_unit_amount, unit_shares) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                position_id, _now(), action, reason, price, quantity, amount,
                avg_price, invested_amount, profit_pct, step,
                raw_unit_amount, adjusted_unit_amount, unit_shares,
            ),
        )
        return int(cur.lastrowid)


def list_orders(position_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    query = 'SELECT o.*, p.ticker FROM orders o JOIN positions p ON p.id = o.position_id'
    args: list[Any] = []
    if position_id is not None:
        query += ' WHERE o.position_id = ?'
        args.append(position_id)
    query += ' ORDER BY o.id DESC LIMIT ?'
    args.append(int(limit))
    with cursor() as conn:
        rows = conn.execute(query, args).fetchall()
    return [dict(r) for r in rows]


def log_signal(*, position_id: int, action: str, reason: str, price: float) -> int:
    with cursor() as conn:
        cur = conn.execute(
            'INSERT INTO signals (position_id, ts, action, reason, price) VALUES (?, ?, ?, ?, ?)',
            (position_id, _now(), action, reason, price),
        )
        return int(cur.lastrowid)


def list_signals(position_id: int | None = None, limit: int = 200) -> list[dict[str, Any]]:
    query = 'SELECT * FROM signals'
    args: list[Any] = []
    if position_id is not None:
        query += ' WHERE position_id = ?'
        args.append(position_id)
    query += ' ORDER BY id DESC LIMIT ?'
    args.append(int(limit))
    with cursor() as conn:
        rows = conn.execute(query, args).fetchall()
    return [dict(r) for r in rows]


# ---- system_state (KV) ------------------------------------------------------

def get_system_state(key: str) -> str | None:
    with cursor() as conn:
        row = conn.execute('SELECT value FROM system_state WHERE key = ?', (key,)).fetchone()
    return row['value'] if row else None


def set_system_state(key: str, value: str) -> None:
    with cursor() as conn:
        conn.execute(
            'INSERT INTO system_state (key, value, updated_at) VALUES (?, ?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
            (key, value, _now()),
        )


def delete_system_state(key: str) -> None:
    with cursor() as conn:
        conn.execute('DELETE FROM system_state WHERE key = ?', (key,))


# ---- equity_snapshots --------------------------------------------------------

def record_equity_snapshot(*, total_asset: float, cash: float, invested: float) -> int:
    with cursor() as conn:
        cur = conn.execute(
            'INSERT INTO equity_snapshots (ts, total_asset, cash, invested) VALUES (?, ?, ?, ?)',
            (_now(), float(total_asset), float(cash), float(invested)),
        )
        return int(cur.lastrowid)


def list_equity_snapshots(limit: int = 500) -> list[dict[str, Any]]:
    with cursor() as conn:
        rows = conn.execute(
            'SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?', (int(limit),)
        ).fetchall()
    return [dict(r) for r in rows]


def get_last_order(position_id: int) -> dict[str, Any] | None:
    with cursor() as conn:
        row = conn.execute(
            'SELECT * FROM orders WHERE position_id = ? ORDER BY id DESC LIMIT 1',
            (position_id,),
        ).fetchone()
    return dict(row) if row else None
