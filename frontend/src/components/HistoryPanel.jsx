import React, { useEffect, useMemo, useState } from 'react';
import { ArrowDownUp } from 'lucide-react';
import Panel from './Panel';
import { fetchEquity, fetchOrders, fetchSignals } from '../api/historyClient.js';

const TEXT = {
  title: '거래 로그',
  subtitle: '상태 메시지',
  tradeLog: '거래 로그',
  messages: '상태 메시지',
  signals: '시그널 로그',
  equity: '자산 추이',
  all: '전체',
  buy: 'BUY',
  sell: 'SELL',
  error: '오류',
  filled: '체결',
  time: '시간',
  action: '액션',
  symbol: '종목',
  price: '가격',
  quantity: '수량',
  amount: '금액',
  avgPrice: '평단가',
  profitPct: '수익률',
  step: '단계',
  reason: '사유',
  noData: '데이터 없음',
};

const TABS = [
  { key: 'trades', label: TEXT.tradeLog },
  { key: 'signals', label: TEXT.signals },
  { key: 'equity', label: TEXT.equity },
  { key: 'messages', label: TEXT.messages },
];

const FILTERS = [
  { key: 'all', label: TEXT.all },
  { key: 'BUY', label: TEXT.buy },
  { key: 'SELL', label: TEXT.sell },
  { key: 'error', label: TEXT.error },
  { key: 'filled', label: TEXT.filled },
];

function filterTrades(trades, filter) {
  const rows = Array.isArray(trades) ? trades : [];
  if (filter === 'BUY' || filter === 'SELL') return rows.filter((t) => t.action === filter);
  if (filter === 'error') return rows.filter((t) => `${t.action || ''} ${t.reason || ''}`.toLowerCase().includes('error'));
  if (filter === 'filled') return rows.filter((t) => t.action === 'BUY' || t.action === 'SELL');
  return rows;
}

function actionClass(action) {
  if (action === 'BUY') return 'trade-action-pill buy';
  if (action === 'SELL') return 'trade-action-pill sell';
  return 'trade-action-pill neutral';
}

function compactTime(ts) {
  if (!ts) return '-';
  const s = String(ts);
  return s.length >= 19 ? s.slice(11, 19) : s;
}

function EquityChart({ data }) {
  if (!Array.isArray(data) || data.length < 2) {
    return <div className="equity-chart-empty">{TEXT.noData}</div>;
  }
  const values = data.map((d) => Number(d.total_asset) || 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const W = 100;
  const H = 60;
  const pad = 4;

  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (W - pad * 2);
    const y = H - pad - ((v - min) / range) * (H - pad * 2);
    return `${x},${y}`;
  });
  const polyline = pts.join(' ');
  const first = values[0];
  const last = values[values.length - 1];
  const changePct = first > 0 ? ((last - first) / first) * 100 : 0;
  const color = changePct >= 0 ? 'var(--green)' : 'var(--red)';

  return (
    <div className="equity-chart-wrap">
      <div className="equity-chart-header">
        <span>총 자산 추이</span>
        <strong style={{ color }}>{changePct >= 0 ? '+' : ''}{changePct.toFixed(2)}%</strong>
      </div>
      <svg className="equity-chart-svg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <polyline points={polyline} fill="none" stroke={color} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      <div className="equity-chart-footer">
        <span>${first.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span>${last.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
      </div>
    </div>
  );
}

export default function HistoryPanel({ activeTab, onTabChange, tradeTabs, trades, messages }) {
  const [tradeFilter, setTradeFilter] = useState('all');
  const [signals, setSignals] = useState([]);
  const [orders, setOrders] = useState([]);
  const [equity, setEquity] = useState([]);

  const filteredTrades = useMemo(() => filterTrades(trades, tradeFilter), [trades, tradeFilter]);
  const displayedTrades = useMemo(() => {
    const rows = filteredTrades.length ? filteredTrades : filterTrades(orders.map((o) => ({
      time: compactTime(o.ts),
      action: o.action,
      symbol: o.ticker || '-',
      price: `$${Number(o.price || 0).toFixed(2)}`,
      quantity: Number(o.quantity || 0).toFixed(6),
      amount: `$${Number(o.amount || 0).toFixed(2)}`,
      avgPrice: `$${Number(o.avg_price || 0).toFixed(2)}`,
      profitPct: `${Number(o.profit_pct || 0) >= 0 ? '+' : ''}${Number(o.profit_pct || 0).toFixed(2)}%`,
      step: String(o.step || 0),
      reason: o.reason || '-',
    })), tradeFilter);
    return rows;
  }, [filteredTrades, orders, tradeFilter]);

  useEffect(() => {
    if (activeTab === 'signals') fetchSignals({ limit: 100 }).then(setSignals);
    if (activeTab === 'equity') fetchEquity({ limit: 200 }).then(setEquity);
    if (activeTab === 'trades') fetchOrders({ limit: 100 }).then(setOrders);
  }, [activeTab]);

  const allTabs = tradeTabs?.length
    ? TABS.filter((t) => tradeTabs.some((tt) => tt.key === t.key) || t.key === 'signals' || t.key === 'equity')
    : TABS;

  return (
    <Panel
      title={TEXT.title}
      subtitle={TEXT.subtitle}
      headerActions={
        <div className="tab-strip">
          {allTabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`tab-button ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => onTabChange(tab.key)}
            >
              {tab.label}
            </button>
          ))}
          <ArrowDownUp size={14} strokeWidth={2.2} />
        </div>
      }
      className="history-panel"
    >
      {activeTab === 'trades' && (
        <>
          <div className="history-tools">
            <div className="history-filter-bar" aria-label="거래 로그 필터">
              {FILTERS.map((filter) => (
                <button
                  key={filter.key}
                  type="button"
                  className={`history-filter-button ${tradeFilter === filter.key ? 'active' : ''}`}
                  onClick={() => setTradeFilter(filter.key)}
                >
                  {filter.label}
                </button>
              ))}
            </div>
            <span className="history-filter-count">{displayedTrades.length} / {(trades || []).length || orders.length}</span>
          </div>
          <table className="data-table history-table">
            <thead>
              <tr>
                <th>{TEXT.time}</th>
                <th>{TEXT.action}</th>
                <th>{TEXT.symbol}</th>
                <th>{TEXT.price}</th>
                <th>{TEXT.quantity}</th>
                <th>{TEXT.amount}</th>
                <th>{TEXT.avgPrice}</th>
                <th>{TEXT.profitPct}</th>
                <th>{TEXT.step}</th>
                <th>{TEXT.reason}</th>
              </tr>
            </thead>
            <tbody>
              {displayedTrades.length === 0 ? (
                <tr><td colSpan={10} className="empty-table-cell">{TEXT.noData}</td></tr>
              ) : displayedTrades.map((trade, i) => (
                <tr key={`${trade.time}-${trade.action}-${i}`}>
                  <td>{trade.time}</td>
                  <td><span className={actionClass(trade.action)}>{trade.action}</span></td>
                  <td>{trade.symbol}</td>
                  <td>{trade.price}</td>
                  <td>{trade.quantity}</td>
                  <td>{trade.amount}</td>
                  <td>{trade.avgPrice}</td>
                  <td className={String(trade.profitPct).startsWith('+') ? 'tone-green' : String(trade.profitPct).startsWith('-') ? 'tone-red' : ''}>
                    {trade.profitPct}
                  </td>
                  <td>{trade.step}</td>
                  <td className="reason-cell">{trade.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {activeTab === 'signals' && (
        <table className="data-table history-table">
          <thead>
            <tr>
              <th>{TEXT.time}</th>
              <th>{TEXT.action}</th>
              <th>{TEXT.price}</th>
              <th>{TEXT.reason}</th>
            </tr>
          </thead>
          <tbody>
            {signals.length === 0 ? (
              <tr><td colSpan={4} className="empty-table-cell">{TEXT.noData}</td></tr>
            ) : signals.map((s) => (
              <tr key={s.id}>
                <td>{compactTime(s.ts)}</td>
                <td><span className={actionClass(s.action)}>{s.action}</span></td>
                <td>{s.price != null ? `$${Number(s.price).toFixed(2)}` : '-'}</td>
                <td className="reason-cell">{s.reason || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {activeTab === 'equity' && <EquityChart data={equity} />}

      {activeTab === 'messages' && (
        <div className="history-message-panel">
          {(messages || []).map((message) => (
            <div key={message} className="history-message-row">
              <span className="message-dot" />
              <span>{message}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
