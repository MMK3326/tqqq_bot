import React from 'react';
import Panel from './Panel';

export default function AssetPanel({ rows }) {
  return (
    <Panel title="자산 현황" subtitle="실시간 요약">
      <table className="data-table asset-table">
        <thead>
          <tr>
            <th>항목</th>
            <th className="align-right">금액 (증감률)</th>
            <th className="align-right">비중</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className={`align-right ${row.amountClass || ''}`}>
                <span>{row.amount}</span>
                {row.note ? <span className={`row-note ${row.noteClass || 'muted'}`}>({row.note})</span> : null}
              </td>
              <td className="align-right muted">{row.ratio}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
