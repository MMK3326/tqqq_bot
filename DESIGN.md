# 자동매매 시스템 설계 문서 (DESIGN.md)

> 이 문서는 Claude Code 및 다른 AI 도구가 프로젝트를 이해하고 일관된 방향으로 작업하기 위한 **단일 진실 공급원(Single Source of Truth)** 입니다.
> 코드 작업을 시작하기 전에 반드시 이 문서를 먼저 읽어주세요.

---

## 1. 프로젝트 목표

다중 종목 × 다중 전략을 운용하는 개인용 자동매매 시스템을 구축한다.

### 핵심 요구사항

1. **다중 종목 운용** — 여러 종목을 동시에 자동매매
2. **종목별 독립 전략** — 종목마다 다른 전략과 다른 파라미터 적용 가능
3. **대시보드 중심 운영** — 종목 추가/수정/활성화는 대시보드에서, 코드 수정 없이
4. **단순한 코드 구조** — 종목별로 모듈을 나누지 않는다. 전략은 로직, 종목은 데이터로 분리
5. **국내 + 해외 주식 동시 지원** — 한국투자증권 KIS API 단일 브로커로 처리

### 비목표 (Non-goals)

- 고빈도매매(HFT), 초단위 미만의 레이턴시 최적화
- 멀티 유저 / 멀티 테넌트 — 개인 사용 전제
- 마이크로서비스화 — 단일 백엔드 프로세스로 충분

---

## 2. 기술 스택

| 영역 | 선택 |
|------|------|
| 백엔드 | Python + FastAPI |
| 프론트엔드 | React (Vite, 기존 코드 활용) |
| DB | SQLite (stdlib `sqlite3`, 개인 사용 규모) |
| 브로커 API | 한국투자증권 KIS Developers (국내 + 해외 통합) |
| 모의 시세 | yfinance (mock 브로커 전용) |
| 스케줄러 | 백엔드 프로세스 내 threading 루프 (Phase 3에서 도입) |

---

## 3. 폴더 구조

```
project-root/
├── DESIGN.md                       # 이 문서
├── backend/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 진입점 (라우터 등록 + DB 초기화 + 시드)
│   ├── config.py                   # 환경변수 로딩 + 경로
│   ├── db.py                       # SQLite 연결 및 단순 쿼리
│   ├── models.py                   # Pydantic 모델 (API 입출력)
│   ├── engine.py                   # 매매 실행 엔진 (사이클 단위 함수)
│   ├── requirements.txt
│   │
│   ├── broker/
│   │   ├── __init__.py             # get_broker() 팩토리
│   │   ├── base.py                 # Broker 추상 인터페이스, MarketData, OrderFill
│   │   ├── mock.py                 # yfinance 기반 가상 매매
│   │   └── kis.py                  # 한국투자증권 KIS (KR + US) — Phase 2에서 구현
│   │
│   ├── strategies/
│   │   ├── __init__.py             # 자동 로딩 registry
│   │   ├── base.py                 # Strategy 추상 클래스, Signal, StrategyContext
│   │   ├── tqqq_split.py           # TQQQ 분할매수/익절
│   │   └── ...                     # 전략은 파일 1개 = 전략 1개
│   │
│   └── api/
│       ├── __init__.py
│       ├── positions.py            # 종목 CRUD API
│       ├── strategies.py           # 전략 목록 API
│       └── dashboard.py            # /api/dashboard + /api/control/* (레거시 호환)
│
└── frontend/                       # 기존 React 코드 (Phase 4에서 다중종목 UI 추가 예정)
    └── src/
        ├── App.jsx
        ├── api/
        ├── components/
        ├── hooks/
        └── data/
```

### 구조 원칙

- **종목별 모듈을 만들지 않는다.** 종목은 DB row이지 코드가 아니다.
- **전략은 파일 1개 = 전략 1개.** 새 전략 추가 시 파일 하나만 추가한다.
- **브로커는 인터페이스 뒤에 숨긴다.** 추후 다른 증권사 추가 가능하도록.

---

## 4. 핵심 컴포넌트 설계

### 4.1 Strategy (전략) — 플러그인 패턴

#### `backend/strategies/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

Action = Literal["BUY", "SELL", "HOLD"]

@dataclass
class Signal:
    action: Action = "HOLD"
    quantity: Optional[float] = None      # 명시 수량 (선택)
    amount: Optional[float] = None        # 명시 금액 (선택, BUY 시 quantity 대신)
    reason: str = ""                      # 로깅용
    extra: dict[str, Any] = field(default_factory=dict)  # 전략별 메타데이터

@dataclass
class StrategyContext:
    """전략이 시장 데이터 외에 참고하는 실행 컨텍스트.

    - state: 현재 포지션 실행 상태 (quantity, avg_price, first_price, bought_steps, ...)
    - budget: 이 종목 할당 예산 (원/달러)
    - cash_balance: 현재 사용 가능한 현금
    """
    state: dict[str, Any]
    budget: float
    cash_balance: float

class Strategy(ABC):
    # 식별자 (파일명과 일치 권장)
    name: str = ""
    # 대시보드 표시명
    display_name: str = ""
    # 대시보드 동적 폼 생성용 파라미터 스키마
    params_schema: dict = {}
    # 지원 시장 ("KR", "US", 또는 둘 다)
    supported_markets: list[str] = ["KR", "US"]

    def __init__(self, params: dict):
        self.params = params

    @abstractmethod
    def generate_signal(self, market_data, context: StrategyContext) -> Signal:
        """현재 시장 데이터 + 포지션 컨텍스트 기반으로 매매 시그널 생성"""
        ...
```

> 참고: 원안에서는 `generate_signal(self, market_data)`만 받았으나, 분할매수처럼
> 포지션 상태(평단가, 매수 단계 등)와 예산 한도가 필요한 전략을 지원하려면
> 두 번째 인자 `context: StrategyContext`가 필요하다.

#### 전략 추가 예시 — `backend/strategies/rsi.py`

```python
from .base import Strategy, Signal, StrategyContext

class RSIStrategy(Strategy):
    name = "rsi"
    display_name = "RSI 과매수/과매도"
    supported_markets = ["KR", "US"]
    params_schema = {
        "period":     {"type": "int",   "default": 14, "label": "RSI 기간",      "min": 2,  "max": 100},
        "oversold":   {"type": "float", "default": 30, "label": "과매도 임계값", "min": 0,  "max": 50},
        "overbought": {"type": "float", "default": 70, "label": "과매수 임계값", "min": 50, "max": 100},
    }

    def generate_signal(self, market_data, context: StrategyContext) -> Signal:
        rsi = market_data.calculate_rsi(self.params["period"])
        if rsi < self.params["oversold"]:
            return Signal(action="BUY", reason=f"RSI={rsi:.1f} < oversold")
        if rsi > self.params["overbought"]:
            return Signal(action="SELL", reason=f"RSI={rsi:.1f} > overbought")
        return Signal()  # HOLD
```

#### Registry 자동 로딩 — `backend/strategies/__init__.py`

```python
import importlib, pkgutil, inspect
from .base import Strategy

REGISTRY: dict[str, type[Strategy]] = {}

# strategies/ 폴더 내 모든 모듈을 자동 스캔
for _, module_name, _ in pkgutil.iter_modules(__path__):
    if module_name == "base":
        continue
    module = importlib.import_module(f".{module_name}", __package__)
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if issubclass(cls, Strategy) and cls is not Strategy and cls.name:
            REGISTRY[cls.name] = cls

def get_strategy(name: str, params: dict) -> Strategy:
    return REGISTRY[name](params)
```

---

### 4.2 Broker (브로커) — 추상화

#### `backend/broker/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class MarketData:
    ticker: str
    market: str
    last_price: float
    history: list[dict[str, Any]] = field(default_factory=list)

@dataclass
class OrderFill:
    ticker: str
    market: str
    action: str
    price: float
    quantity: float
    amount: float
    ts: str

class Broker(ABC):
    @abstractmethod
    def get_market_data(self, ticker: str, market: str, lookback: int = 100) -> MarketData: ...

    @abstractmethod
    def get_current_price(self, ticker: str, market: str) -> float: ...

    @abstractmethod
    def place_order(self, ticker: str, market: str, side: str, quantity: float,
                    price: Optional[float] = None) -> OrderFill: ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_balance(self) -> dict[str, Any]: ...
```

#### `backend/broker/kis.py`

한국투자증권 KIS Developers API 구현. 국내/해외 분기는 내부에서 처리.

```python
class KISBroker(Broker):
    def __init__(self, app_key: str, app_secret: str, account_no: str, is_paper: bool = True):
        ...

    def get_market_data(self, ticker, market, lookback=100):
        if market == "KR":
            return self._kr_chart(ticker, lookback)
        elif market == "US":
            return self._us_chart(ticker, lookback)
```

**주의:** KIS API는 국내/해외 엔드포인트가 다르고, 모의투자/실전 분기도 필요. `is_paper` 플래그 필수.

#### `backend/broker/mock.py`

yfinance로 현재가를 조회하고, 주문은 즉시 체결되는 것으로 가상 처리한다.
상태(보유 수량/평단가 등)는 broker가 들고 있지 않고 엔진이 `positions.state` JSON 컬럼에 저장한다.

---

### 4.3 종목 데이터 모델

#### DB 스키마 — `positions` 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INTEGER PK | 자동 생성 |
| ticker | TEXT | "005930", "AAPL" |
| market | TEXT | "KR" or "US" |
| name | TEXT | 표시용 종목명 |
| strategy | TEXT | strategy.name |
| params | TEXT (JSON) | 전략 파라미터 |
| budget | REAL | 해당 종목 할당 예산 (원 또는 달러) |
| enabled | INTEGER | 활성 여부 (0/1) |
| state | TEXT (JSON) | 실행 상태: quantity, avg_price, first_price, invested_amount, bought_steps, cycle_count |
| created_at | TEXT | ISO 시간 |
| updated_at | TEXT | ISO 시간 |

> 참고: 원안의 `positions`는 설정만 담는 테이블이었으나, 매 사이클마다 다시 계산하기 비싼
> 실행 상태(평단가/매수 단계 등)는 같은 row의 `state` JSON 컬럼에 캐시한다.
> 진실의 원천은 `orders` 테이블이며, `state`는 도출 가능한 캐시다.

#### 보조 테이블

- `orders` — 주문 이력 (자동 + 수동)
- `signals` — 전략이 생성한 시그널 로그 (디버깅용)
- `equity_snapshots` — 자산 추이 (일별 또는 시간별)

---

### 4.4 Engine (실행 엔진)

#### `backend/engine.py`

```python
def run_cycle(broker) -> list:
    """매 사이클마다 실행: 활성 종목 → 전략 → 시그널 → 주문 → 상태 갱신"""
    results = []
    for pos in db.list_positions(enabled_only=True):
        try:
            strategy = get_strategy(pos["strategy"], pos["params"])
            data = broker.get_market_data(pos["ticker"], pos["market"], lookback=100)
            context = StrategyContext(
                state=pos["state"],
                budget=pos["budget"],
                cash_balance=max(0.0, pos["budget"] - pos["state"].get("invested_amount", 0.0)),
            )
            signal = strategy.generate_signal(data, context)

            db.log_signal(position_id=pos["id"], action=signal.action,
                          reason=signal.reason, price=data.last_price)

            if signal.action == "HOLD":
                results.append({"position_id": pos["id"], "signal": signal})
                continue

            # 주문 → 상태 갱신 → orders 로그
            fill = broker.place_order(pos["ticker"], pos["market"], signal.action, ...)
            new_state = apply_order_to_state(pos["state"], fill, signal)
            db.update_position_state(pos["id"], new_state)
            db.log_order(...)
            results.append({"position_id": pos["id"], "order": fill})
        except Exception as e:
            results.append({"position_id": pos["id"], "error": str(e)})
            # 한 종목 실패가 다른 종목에 영향 주지 않도록
    return results
```

#### 스케줄링

- 국내 장중 (09:00–15:30 KST) — 1분 또는 5분 주기
- 미국 장중 (23:30–06:00 KST, 서머타임 22:30–05:00) — 동일
- 장 마감 후에는 휴식 (불필요한 API 호출 방지)

> Phase 1에서는 `run_cycle`만 제공하고, 자동 스케줄러와 장 시간 인식은 Phase 3에서 도입한다.

---

## 5. API 엔드포인트 (대시보드 ↔ 백엔드)

### 종목 관리

- `GET    /api/positions` — 전체 종목 목록
- `POST   /api/positions` — 새 종목 추가
- `PATCH  /api/positions/{id}` — 수정 (파라미터, enabled 토글 등)
- `DELETE /api/positions/{id}` — 삭제

### 전략 정보

- `GET /api/strategies` — 등록된 전략 목록 + `params_schema`
  - 대시보드는 이 응답으로 종목 추가 폼의 동적 필드를 그린다.

### 모니터링 / 레거시

- `GET  /api/dashboard` — 레거시 단일종목 요약 페이로드 (현재 프론트엔드가 사용)
- `POST /api/control/{action}` — start | pause | run-once | refresh | close
- `GET  /api/dashboard/summary` — Phase 4에서 다중종목 요약으로 신설 예정
- `GET  /api/orders?limit=50` — Phase 4
- `GET  /api/signals?position_id=X` — Phase 4
- `GET  /api/equity?range=30d` — Phase 4

---

## 6. 대시보드 UX 흐름

### 6.1 종목 추가 (Phase 4에서 UI 구현)

1. 대시보드에서 `[+ 종목 추가]` 클릭
2. 폼 표시:
   - 시장 (KR / US)
   - 종목코드 → 종목명 자동 조회 (KIS API)
   - 전략 선택 (드롭다운, `/api/strategies`에서 받아온 목록)
   - 전략 선택 시 → `params_schema` 기반으로 입력 필드 동적 생성
   - 예산 입력
   - 활성화 체크박스
3. `[저장]` → `POST /api/positions`
4. 다음 엔진 사이클부터 자동 반영 (재시작 불필요)

### 6.2 전략 추가 (개발자 작업)

1. `backend/strategies/` 폴더에 새 .py 파일 추가
2. `Strategy` 상속, `name`/`display_name`/`params_schema`/`generate_signal` 구현
3. 백엔드 재시작
4. 대시보드 새로고침 → 전략 드롭다운에 자동 표시

---

## 7. 환경 설정 / 시크릿

### `.env` (예시, 절대 커밋 금지)

```
BROKER=mock                  # mock | kis
KIS_APP_KEY=...
KIS_APP_SECRET=...
KIS_ACCOUNT_NO=...
KIS_IS_PAPER=true            # 모의투자 여부 (개발 중에는 반드시 true)
DB_PATH=./data/trading.db
ENGINE_INTERVAL_SECONDS=60
TOTAL_CAPITAL=3400.0         # 대시보드 표시용 (Phase 4에서 portfolio 테이블로 이전)
```

### `.gitignore` 필수 항목

```
.env
*.db
data/
__pycache__/
node_modules/
```

---

## 8. 안전 장치 (반드시 구현)

자동매매는 사고가 났을 때 손실이 크므로 다음 안전장치가 필수.

1. **모의투자 우선** — `KIS_IS_PAPER=true` 기본값. 실전 전환은 명시적 설정.
2. **일일 최대 손실 한도** — 한도 도달 시 엔진 자동 정지 (kill switch)
3. **종목별 예산 상한** — `budget` 컬럼으로 강제
4. **시그널 ↔ 주문 분리 로깅** — 시그널이 발생해도 주문이 실패할 수 있음
5. **장 외 시간 주문 차단** — 엔진에서 시장 시간 체크
6. **수동 비상 정지** — 대시보드에 "전체 정지" 버튼
7. **주문 멱등성** — 같은 시그널로 중복 주문 방지 (시간 윈도우 기반)

> Phase 1에서는 (3)·(4)만 구현되고 나머지는 Phase 3에서 도입한다.

---

## 9. 마이그레이션 작업 순서 (Claude Code용 체크리스트)

### Phase 0: 현황 파악
- [x] 기존 백엔드 스택 / 폴더 구조 / 의존성 분석
- [x] 기존 프론트엔드(React) 구조 분석
- [x] 이 문서의 "기술 스택" 표 갱신
- [x] 갭 분석 보고서 작성: 현재 → 목표 차이

### Phase 1: 백엔드 골격
- [x] 폴더 구조 위 설계대로 재정렬
- [x] `Strategy` base 클래스 + registry 자동 로딩 구현
- [x] 기존 TQQQ 운용 전략을 `tqqq_split`로 이식 (예시 전략 추가는 Phase 2 이후)
- [x] `Broker` 인터페이스 + `MockBroker`(yfinance) + `KISBroker` 스켈레톤
- [x] SQLite DB 스키마 (positions/orders/signals/equity_snapshots) + 자동 생성 + TQQQ 시드
- [x] FastAPI 엔드포인트 (`positions` CRUD, `strategies` 목록)
- [x] 레거시 `/api/dashboard` + `/api/control/*` 호환 유지 (DB-backed 재구현)

### Phase 2: KIS API 연동
- [ ] 토큰 발급 / 갱신
- [ ] 국내 시세 조회
- [ ] 해외 시세 조회
- [ ] 국내 주문
- [ ] 해외 주문
- [ ] 잔고 / 보유종목 조회
- [ ] 모든 호출에 모의/실전 분기

### Phase 3: 엔진 + 안전장치
- [x] 사이클 함수 (`engine.run_cycle`) — 활성 종목 전체 사이클 + 결과 격리
- [x] 자동 루프(`DashboardState._loop`) — 장 시간 차단은 SafetyGate 통과 시점에 적용
- [x] 시그널/주문 분리 로깅 + blocked 사유 메시지 출력
- [x] 안전장치 (`backend/safety.py`):
  - [x] 전역 kill switch (DB `system_state` KV에 영구 저장)
  - [x] 일일 손실 한도 자동 트립 (baseline asset 대비 `DAILY_LOSS_LIMIT_PCT`)
  - [x] 장 시간 차단 (`MARKET_HOURS_STRICT`, KR 09:00-15:30 KST / US 09:30-16:00 ET)
  - [x] 주문 멱등성 (`ORDER_IDEMPOTENCY_WINDOW_SEC`, 같은 종목×동일 action)
- [x] equity_snapshot 자동 기록 (매 사이클 1회)
- [x] `POST /api/control/kill-switch` / `POST /api/control/kill-switch/reset`
- [ ] 시장 휴장일 캘린더 (Phase 5에서 추가)

### Phase 4: 대시보드 연동
- [ ] 다중 종목 목록 / 추가 / 수정 / 삭제 UI
- [ ] 전략 동적 폼 (params_schema 기반)
- [ ] 자산 추이 / 주문 이력 / 시그널 로그 화면
- [ ] 비상 정지 버튼

### Phase 5: 검증
- [ ] 모의투자로 1주 이상 운영
- [ ] 로그 분석 / 버그 수정
- [ ] 실전 전환 체크리스트

---

## 10. 변경 관리

이 문서를 수정해야 할 일이 생기면 **코드 수정 전에 이 문서를 먼저 갱신**한다.
설계 변경 → 문서 갱신 → 코드 변경 순서를 지킬 것.

문서와 코드가 어긋났을 때는 문서가 의도, 코드가 현실이므로 어느 쪽이 맞는지 사용자에게 확인 후 한쪽을 맞춘다.
