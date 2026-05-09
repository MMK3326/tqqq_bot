import React, { useMemo, useState } from 'react';
import { ArrowDownUp } from 'lucide-react';
import Panel from './Panel';

const TEXT = {
  title: '\uac70\ub798 \ub85c\uadf8',
  subtitle: '\uc0c1\ud0dc \uba54\uc2dc\uc9c0',
  tradeLog: '\uac70\ub798 \ub85c\uadf8',
  messages: '\uc0c1\ud0dc \uba54\uc2dc\uc9c0',
  all: '\uc804\uccb4',
  buy: 'BUY',
  sell: 'SELL',
  error: '\uc624\ub958',
  filled: '\uccb4\uacb0',
  time: '\uc2dc\uac04',
  action: '\uc561\uc158',
  symbol: '\uc885\ubaa9',
  price: '\uac00\uaca9',
  quantity: '\uc218\ub7c9',
  amount: '\uae08\uc561',
  avgPrice: '\ud3c9\ub2e8\uac00',
  profitPct: '\uc218\uc775\ub960',
  step: '\ub2e8\uacc4',
  reason: '\uc0ac\uc720',
};

const FILTERS = [
  { key: 'all', label: TEXT.all },
  { key: 'BUY', label: TEXT.buy },
  { key: 'SELL', label: TEXT.sell },
  { key: 'error', label: TEXT.error },
  { key: 'filled', label: TEXT.filled },
];

function filterTrades(trades, filter) {
  const rows = Array.isArray(trades) ? trades : [];
  if (filter === 'BUY' || filter === 'SELL') return rows.filter((trade) => trade.action === filter);
  if (filter === 'error') {
    return rows.filter((trade) => {
      const text = `${trade.action || ''} ${trade.reason || ''}`.toLowerCase();
      return text.includes('error') || text.includes('\uc624\ub958');
    });
  }
  if (filter === 'filled') return rows.filter((trade) => trade.action === 'BUY' || trade.action === 'SELL');
  return rows;
}

function actionClass(action) {
  if (action === 'BUY') return 'trade-action-pill buy';
  if (action === 'SELL') return 'trade-action-pill sell';
  return 'trade-action-pill neutral';
}

export default function HistoryPanel({ activeTab, onTabChange, tradeTabs, trades, messages }) {
  const [tradeFilter, setTradeFilter] = useState('all');
  const filteredTrades = useMemo(() => filterTrades(trades, tradeFilter), [trades, tradeFilter]);

  return (
    <Panel
      title={TEXT.title}
      subtitle={TEXT.subtitle}
      headerActions={
        <div className="tab-strip">
          {tradeTabs.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`tab-button ${activeTab === tab.key ? 'active' : ''}`}
              onClick={() => onTabChange(tab.key)}
            >
              {tab.key === 'trades' ? TEXT.tradeLog : TEXT.messages}
            </button>
          ))}
          <ArrowDownUp size={14} strokeWidth={2.2} />
        </div>
      }
      className="history-panel"
    >
      {activeTab === 'trades' ? (
        <>
          <div className="history-tools">
            <div className="history-filter-bar" aria-label="\uac70\ub798 \ub85c\uadf8 \ud544\ud130">
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
            <span className="history-filter-count">{filteredTrades.length} / {(trades || []).length}</span>
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
              {filteredTrades.map((trade) => (
                <tr key={`${trade.time}-${trade.action}-${trade.reason}`}>
                  <td>{trade.time}</td>
                  <td><span className={actionClass(trade.action)}>{trade.action}</span></td>
                  <td>{trade.symbol}</td>
                  <td>{trade.price}</td>
                  <td>{trade.quantity}</td>
                  <td>{trade.amount}</td>
                  <td>{trade.avgPrice}</td>
                  <td className={trade.profitPct.startsWith('+') ? 'tone-green' : trade.profitPct.startsWith('-') ? 'tone-red' : ''}>
                    {trade.profitPct}
                  </td>
                  <td>{trade.step}</td>
                  <td className="reason-cell">{trade.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      ) : (
        <div className="history-message-panel">
          {messages.map((message) => (
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
