import React from 'react';
import Panel from './Panel';

export default function PerformancePanel({ rows }) {
  return (
    <Panel title="누적 성과" subtitle="사이클 통계">
      <div className="performance-list">
        {rows.map((row) => (
          <div key={row.label} className={`performance-row ${row.tone ? row.tone : ''}`}>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
    </Panel>
  );
}
