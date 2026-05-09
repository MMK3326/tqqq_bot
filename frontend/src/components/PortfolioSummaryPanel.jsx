import React from 'react';
import Panel from './Panel';
import { getValueClass, safeDisplay } from '../data/symbolRows.js';

const TEXT = {
  title: '\ud3ec\ud2b8\ud3f4\ub9ac\uc624 \uc694\uc57d',
  subtitle: '\uc804\uccb4 \uacc4\uc815 \uae30\uc900',
  updated: '\uc5c5\ub370\uc774\ud2b8',
  totalAsset: '\ucd1d \uc790\uc0b0',
  cash: '\uc608\uc218\uae08',
  invested: '\ucd1d \ud22c\uc785\uae08',
  available: '\uac00\uc6a9 \uae08\uc561',
  realized: '\ucd1d \uc2e4\ud604\uc190\uc775',
  unrealized: '\ucd1d \ubbf8\uc2e4\ud604\uc190\uc775',
  totalReturn: '\uc804\uccb4 \uc218\uc775\ub960',
};

const ROW_MAP = [
  { label: TEXT.totalAsset, index: 0, valueKey: 'amount', subKey: 'note', emphasis: true },
  { label: TEXT.cash, index: 1, valueKey: 'amount', subKey: 'ratio' },
  { label: TEXT.invested, index: 3, valueKey: 'amount', subKey: 'ratio' },
  { label: TEXT.available, index: 4, valueKey: 'amount', subKey: 'ratio' },
  { label: TEXT.realized, index: 6, valueKey: 'amount', subKey: 'note', valueIsChange: true, emphasis: true },
  { label: TEXT.unrealized, index: 5, valueKey: 'amount', subKey: 'note', valueIsChange: true, emphasis: true },
  { label: TEXT.totalReturn, index: 0, valueKey: 'note', valueIsChange: true },
  { label: 'MDD', index: 8, valueKey: 'amount', valueIsChange: true, emphasis: true },
];

function valueTone(item, value) {
  if (!item.valueIsChange) return '';
  if (item.label === 'MDD' && String(value || '').startsWith('-')) return 'tone-red';
  return getValueClass(value);
}

function buildRows(accountRows) {
  return ROW_MAP.map((item) => {
    const row = accountRows?.[item.index] || {};
    const value = row[item.valueKey];
    const subValue = item.subKey ? row[item.subKey] : '';
    return {
      label: item.label,
      value: safeDisplay(value),
      subValue: subValue ? safeDisplay(subValue) : '',
      tone: valueTone(item, value),
      subTone: getValueClass(subValue),
      emphasis: Boolean(item.emphasis),
    };
  });
}

export default function PortfolioSummaryPanel({ data }) {
  const rows = buildRows(data?.accountRows || []);

  return (
    <Panel title={TEXT.title} subtitle={TEXT.subtitle} className="portfolio-summary-panel">
      <div className="portfolio-summary-list">
        {rows.map((row) => (
          <div key={row.label} className={`portfolio-summary-row ${row.emphasis ? 'is-emphasis' : ''}`}>
            <span className="portfolio-label">{row.label}</span>
            <div className="portfolio-value-wrap">
              <strong className={row.tone}>{row.value}</strong>
              {row.subValue ? <small className={row.subTone}>({row.subValue})</small> : null}
            </div>
          </div>
        ))}
      </div>

      <div className="portfolio-updated">
        {TEXT.updated}: {safeDisplay(data?.lastPriceTime)}
      </div>
    </Panel>
  );
}
