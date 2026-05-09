import React from 'react';
import { BarChart3, Diamond } from 'lucide-react';

export default function HeaderBar({ title }) {
  return (
    <div className="title-row">
      <div className="brand-mark" aria-hidden="true">
        <Diamond size={17} strokeWidth={2.1} />
      </div>
      <div className="title-copy">
        <div className="eyebrow">TQQQ 자동매매</div>
        <h1>{title}</h1>
      </div>
      <div className="title-meta">
        <BarChart3 size={17} />
        <span>BINANCE / TRADINGVIEW DARK</span>
      </div>
    </div>
  );
}
