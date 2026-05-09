import React from 'react';
import Panel from './Panel';

export default function SystemPanel({ rows }) {
  return (
    <Panel title="시스템 정보" subtitle="상태 및 주기">
      <div className="system-list">
        {rows.map((row) => (
          <div key={row.label} className="system-row">
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
      </div>
    </Panel>
  );
}
