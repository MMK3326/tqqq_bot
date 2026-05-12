"""FastAPI 진입점. DB 초기화 → TQQQ 시드 → 라우터 등록.

실행:
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8008
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config, db
from .api import dashboard as dashboard_api
from .api import history as history_api
from .api import positions as positions_api
from .api import strategies as strategies_api


def _seed_default_position() -> None:
    """positions 테이블이 비어 있으면 TQQQ 1개를 시드한다.

    기존 사용자 운용 흐름(TQQQ 분할매수)을 그대로 이어가기 위함이며,
    이미 종목이 하나라도 있으면 아무 일도 하지 않는다.
    """
    if db.list_positions():
        return
    db.insert_position(
        ticker='TQQQ',
        market='US',
        name='TQQQ 분할매수 데모',
        strategy='tqqq_split',
        params={
            'base_split_count': 40,
            'drop_interval_pct': 0.5,
            'take_profit_pct': 0.5,
            'use_integer_share_unit': True,
        },
        budget=config.TOTAL_CAPITAL * 0.70,
        enabled=True,
    )


config.ensure_data_dir()
db.init_schema()
_seed_default_position()


app = FastAPI(title='MMK AutoBot API', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(positions_api.router)
app.include_router(strategies_api.router)
app.include_router(history_api.router)
app.include_router(dashboard_api.router)


@app.get('/health')
def health():
    return {'status': 'ok'}
