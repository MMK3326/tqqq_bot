import React from 'react';
import { getValueClass, safeDisplay } from '../data/symbolRows.js';

const TEXT = {
  title: '\uc804\uccb4 \uc131\uacfc \uc694\uc57d',
  completedCycles: '\uc644\ub8cc \uc0ac\uc774\ud074',
  totalTrades: '\ucd1d \uac70\ub798',
  winRate: '\uc2b9\ub960',
  avgCycleReturn: '\ud3c9\uade0 \uc0ac\uc774\ud074 \uc218\uc775\ub960',
  bestReturn: '\ucd5c\uace0 \uc218\uc775\ub960',
  maxCapital: '\ucd5c\ub300 \uc790\uae08 \ube44\uc911',
};

function totalTrades(rows) {
  const buys = Number.parseInt(rows?.[1]?.value || '0', 10);
  const sells = Number.parseInt(rows?.[2]?.value || '0', 10);
  const total = buys + sells;
  return Number.isFinite(total) ? String(total) : '-';
}

function buildKpis(rows) {
  return [
    { label: TEXT.completedCycles, value: rows?.[0]?.value },
    { label: TEXT.totalTrades, value: totalTrades(rows) },
    { label: TEXT.winRate, value: rows?.[5]?.value },
    { label: TEXT.avgCycleReturn, value: rows?.[6]?.value },
    { label: TEXT.bestReturn, value: rows?.[7]?.value },
    { label: TEXT.maxCapital, value: rows?.[9]?.value },
    { label: 'MDD', value: rows?.[11]?.value },
  ];
}

export default function PerformanceKpiStrip({ rows }) {
  const kpis = buildKpis(rows || []);

  return (
    <section className="performance-kpi-strip">
      <div className="performance-kpi-title">{TEXT.title}</div>
      {kpis.map((item) => (
        <div key={item.label} className="performance-kpi-card">
          <span>{item.label}</span>
          <strong className={item.label === 'MDD' && String(item.value || '').startsWith('-') ? 'tone-red' : getValueClass(item.value)}>
            {safeDisplay(item.value)}
          </strong>
        </div>
      ))}
    </section>
  );
}
