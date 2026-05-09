import React from 'react';
import { toneClass } from '../utils/format';

export default function MetricStrip({ cards }) {
  return (
    <section className="metric-strip" aria-label="핵심 지표">
      {cards.map((card) => (
        <article key={card.label} className={`metric-card ${toneClass(card.tone)}`}>
          <span className="metric-label">{card.label}</span>
          <span className="metric-value">{card.value}</span>
          {card.subValue ? <span className="metric-sub">{card.subValue}</span> : <span className="metric-sub spacer" />}
        </article>
      ))}
    </section>
  );
}
