import React from 'react';
import { formatPercent, formatPrice, formatQuantity, formatSignedPercent, formatUnit, getStatusClass, safeDisplay, toNumber } from '../data/symbolRows.js';

const TEXT = {
  title: '\uc120\ud0dd \uc885\ubaa9 \uc0c1\uc138',
  empty: '\uc120\ud0dd\ub41c \uc885\ubaa9\uc774 \uc5c6\uc2b5\ub2c8\ub2e4',
  currentPrice: '\ud604\uc7ac\uac00',
  initialEntryPrice: '\ucd08\uae30 \uc9c4\uc785\uac00',
  avgPrice: '\ud3c9\ub2e8\uac00',
  quantity: '\ubcf4\uc720 \uc218\ub7c9',
  investedAmount: '\ud22c\uc785\uae08',
  allocation: '\ud604\uc7ac \ube44\uc911',
  investedUnit: '\ud22c\uc785 Unit',
  strategyStatus: '\uc804\ub7b5 \uc0c1\ud0dc',
  nextBuy: '\ub2e4\uc74c \ucd94\uac00\ub9e4\uc218',
  nextTakeProfit: '\ub2e4\uc74c \uc775\uc808',
  strategySummary: '\uc804\ub7b5 \uc694\uc57d',
  volatility: '\ubcc0\ub3d9\uc131 \ucd94\uc885 \uad6c\uac04\ubcc4 \ub9e4\ub9e4',
  chartTitle: '\uac00\uaca9 \ub808\ubca8',
};

function buildPriceLevels(data) {
  return [
    { key: 'buy', label: TEXT.nextBuy, value: toNumber(data.nextBuyPrice), className: 'tone-yellow' },
    { key: 'entry', label: TEXT.initialEntryPrice, value: toNumber(data.initialEntryPrice ?? data.firstPrice), className: 'tone-blue' },
    { key: 'avg', label: TEXT.avgPrice, value: toNumber(data.avgPrice), className: 'tone-blue' },
    { key: 'current', label: TEXT.currentPrice, value: toNumber(data.currentPrice), className: 'tone-green' },
    { key: 'take', label: TEXT.nextTakeProfit, value: toNumber(data.nextTakeProfitPrice), className: 'tone-green' },
  ].filter((item) => item.value !== null);
}

function MiniPriceChart({ data }) {
  const levels = buildPriceLevels(data);
  if (!levels.length) {
    return (
      <div className="mini-price-chart">
        <div className="mini-chart-header">{TEXT.chartTitle}</div>
        <div className="mini-chart-empty">-</div>
      </div>
    );
  }

  const values = levels.map((item) => item.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || Math.max(max * 0.01, 1);
  const point = (index, value) => {
    const x = 14 + index * (172 / Math.max(levels.length - 1, 1));
    const y = 58 - ((value - min) / range) * 42;
    return `${x},${y}`;
  };
  const points = levels.map((item, index) => point(index, item.value)).join(' ');

  return (
    <div className="mini-price-chart">
      <div className="mini-chart-header">{TEXT.chartTitle}</div>
      <svg className="mini-chart-svg" viewBox="0 0 200 72" role="img" aria-label="\uc885\ubaa9 \uac00\uaca9 \ub808\ubca8">
        <line x1="14" y1="58" x2="186" y2="58" className="mini-chart-grid" />
        <polyline points={points} className="mini-chart-line" />
        {levels.map((item, index) => {
          const [cx, cy] = point(index, item.value).split(',');
          return <circle key={item.key} cx={cx} cy={cy} r="3.5" className={`mini-chart-dot ${item.key}`} />;
        })}
      </svg>
      <div className="mini-chart-legend">
        {levels.map((item) => (
          <span key={item.key} className={item.className}>
            {item.label} {formatPrice(item.value)}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function SymbolDetailCard({ symbol }) {
  if (!symbol) {
    return (
      <section className="panel symbol-detail-panel">
        <div className="symbol-detail-title-row">
          <h2>{TEXT.title}</h2>
        </div>
        <p className="symbol-detail-description">{TEXT.empty}</p>
      </section>
    );
  }

  const data = symbol || {};
  const topItems = [
    [TEXT.currentPrice, formatPrice(data.currentPrice), 'detail-current-price'],
    [TEXT.initialEntryPrice, formatPrice(data.initialEntryPrice ?? data.firstPrice), 'detail-entry-price'],
    [TEXT.avgPrice, formatPrice(data.avgPrice), 'detail-avg-price'],
    [TEXT.quantity, formatQuantity(data.quantity), ''],
    [TEXT.investedAmount, formatPrice(data.investedAmount), ''],
    [TEXT.allocation, formatPercent(data.allocation), ''],
    [TEXT.investedUnit, formatUnit(data.investedUnit ?? data.stage), 'tone-blue'],
    [TEXT.strategyStatus, safeDisplay(data.strategyStatus), getStatusClass(data.strategyStatus)],
  ];

  return (
    <section className="panel symbol-detail-panel">
      <div className="symbol-detail-title-row">
        <h2>{TEXT.title}</h2>
        <span className="symbol-badge">{safeDisplay(data.symbol)}</span>
      </div>
      <p className="symbol-detail-description">{data.name || data.description || '-'}</p>

      <div className="symbol-detail-top-grid">
        {topItems.map(([label, value, tone], index) => (
          <div key={label} className={`symbol-detail-top-item ${index === topItems.length - 1 ? 'last' : ''}`}>
            <span>{label}</span>
            <strong className={tone}>{value}</strong>
          </div>
        ))}
      </div>

      <div className="symbol-detail-bottom-grid">
        <div className="symbol-detail-bottom-item price-target buy-target">
          <span>{TEXT.nextBuy}</span>
          <strong className="tone-yellow">{formatPrice(data.nextBuyPrice)}</strong>
          <small>{formatSignedPercent(data.nextBuyRate)}</small>
        </div>
        <div className="symbol-detail-bottom-item price-target take-target">
          <span>{TEXT.nextTakeProfit}</span>
          <strong className="tone-green">{formatPrice(data.nextTakeProfitPrice)}</strong>
          <small>{formatSignedPercent(data.nextTakeProfitRate)}</small>
        </div>
        <div className="symbol-detail-summary">
          <span>{TEXT.strategySummary}</span>
          <strong>{safeDisplay(data.strategySummary)}</strong>
          <small>{TEXT.volatility}</small>
        </div>
        <MiniPriceChart data={data} />
      </div>
    </section>
  );
}
