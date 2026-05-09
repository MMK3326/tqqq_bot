import React from 'react';
import Panel from './Panel';
import { formatMoney, formatPercent, formatPrice, formatSignedPercent, formatUnit, getStatusClass, getValueClass, safeDisplay } from '../data/symbolRows.js';

const TEXT = {
  title: '\uc885\ubaa9\ubcc4 \uc6b4\uc6a9 \ud604\ud669',
  subtitle: '\ubcf4\uc720 \ubc0f \uc6b4\uc6a9 \uc911\uc778 \uc885\ubaa9 \ub9ac\uc2a4\ud2b8',
  countSuffix: '\uac1c \uc885\ubaa9',
  symbol: '\uc885\ubaa9',
  status: '\uc0c1\ud0dc',
  currentPrice: '\ud604\uc7ac\uac00',
  initialEntryPrice: '\ucd08\uae30 \uc9c4\uc785\uac00',
  returnRate: '\uc218\uc775\ub960',
  unrealizedPnl: '\ud3c9\uac00\uc190\uc775',
  allocation: '\ube44\uc911',
  investedUnit: '\ud22c\uc785 Unit',
  nextBuy: '\ub2e4\uc74c \ub9e4\uc218',
  nextTakeProfit: '\ub2e4\uc74c \uc775\uc808',
  action: '\uc561\uc158',
  empty: '\uc6b4\uc6a9 \uc911\uc778 \uc885\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4',
  detail: '\uc0c1\uc138',
  guide: '* \ud45c\uc5d0\uc11c \uc885\ubaa9\uc744 \uc120\ud0dd\ud558\uba74 \uc0c1\uc138 \uc815\ubcf4\uac00 \ud45c\uc2dc\ub429\ub2c8\ub2e4.',
};

export default function SymbolOperationsTable({ symbols, selectedSymbol, onSelectSymbol }) {
  const rows = Array.isArray(symbols) ? symbols : [];

  return (
    <Panel
      title={TEXT.title}
      subtitle={TEXT.subtitle}
      className="symbol-table-panel"
      headerActions={<span className="panel-count">{rows.length}{TEXT.countSuffix}</span>}
    >
      <div className="symbol-table-scroll">
        <table className="data-table symbol-table">
          <thead>
            <tr>
              <th>{TEXT.symbol}</th>
              <th>{TEXT.status}</th>
              <th className="align-right">{TEXT.currentPrice}</th>
              <th className="align-right">{TEXT.initialEntryPrice}</th>
              <th className="align-right">{TEXT.returnRate}</th>
              <th className="align-right">{TEXT.unrealizedPnl}</th>
              <th className="align-right">{TEXT.allocation}</th>
              <th className="align-right">{TEXT.investedUnit}</th>
              <th className="align-right">{TEXT.nextBuy}</th>
              <th className="align-right">{TEXT.nextTakeProfit}</th>
              <th className="align-right">{TEXT.action}</th>
            </tr>
          </thead>
          <tbody>
            {!rows.length ? (
              <tr>
                <td colSpan={11} className="empty-table-cell">{TEXT.empty}</td>
              </tr>
            ) : rows.map((row) => (
              <tr
                key={row.symbol}
                className={selectedSymbol === row.symbol ? 'selected-row' : ''}
                onClick={() => onSelectSymbol?.(row.symbol)}
              >
                <td>
                  <div className="symbol-name-cell">
                    <strong>{row.symbol}</strong>
                    <span>{row.name || row.description || '-'}</span>
                  </div>
                </td>
                <td>
                  <span className={`state-pill ${getStatusClass(row.status)}`}>{safeDisplay(row.status)}</span>
                </td>
                <td className="align-right numeric-cell">{formatPrice(row.currentPrice)}</td>
                <td className="align-right numeric-cell tone-blue">{formatPrice(row.initialEntryPrice ?? row.firstPrice)}</td>
                <td className={`align-right numeric-cell ${getValueClass(row.returnRate)}`}>{formatSignedPercent(row.returnRate)}</td>
                <td className={`align-right numeric-cell ${getValueClass(row.unrealizedPnl)}`}>{formatMoney(row.unrealizedPnl)}</td>
                <td className="align-right numeric-cell">{formatPercent(row.allocation)}</td>
                <td className="align-right">
                  <span className="state-pill state-buy">{formatUnit(row.investedUnit ?? row.stage)}</span>
                </td>
                <td className="align-right numeric-cell tone-yellow">
                  {formatPrice(row.nextBuyPrice)}
                  <span className="rate-note">{formatSignedPercent(row.nextBuyRate)}</span>
                </td>
                <td className="align-right numeric-cell tone-green">
                  {formatPrice(row.nextTakeProfitPrice)}
                  <span className="rate-note">{formatSignedPercent(row.nextTakeProfitRate)}</span>
                </td>
                <td className="align-right">
                  <button
                    type="button"
                    className="table-action-button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelectSymbol?.(row.symbol);
                    }}
                  >
                    {TEXT.detail}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-guide">{TEXT.guide}</div>
    </Panel>
  );
}
