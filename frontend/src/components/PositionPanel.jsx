import React from 'react';
import { ChevronRight, Star } from 'lucide-react';
import Panel from './Panel';

const METRICS = [
  ['현재가', 'currentPrice'],
  ['평단가', 'avgPrice'],
  ['보유 수량', 'quantity'],
  ['총 투입금', 'investedAmount'],
  ['현재 자금 비중', 'investedPct'],
];

const LEVELS = [
  { label: '현재 단계', key: 'currentStep', tone: 'tone-blue', noteKey: null },
  { label: '다음 추가매수', key: 'nextBuyPrice', tone: 'tone-yellow', noteKey: 'nextBuyNote' },
  { label: '다음 익절', key: 'nextTakeProfitPrice', tone: 'tone-green', noteKey: 'nextTakeProfitNote' },
];

const STATS = [
  ['누적 실현손익', 'realized', 'tone-green'],
  ['누적 수익률', 'realizedPct', 'tone-green'],
  ['거래 횟수', 'tradeCount', ''],
  ['매수 횟수', 'buyCount', ''],
  ['매도 횟수', 'sellCount', ''],
  ['승리', 'winCount', ''],
  ['승률', 'winRate', ''],
  ['평균 사이클 수익률', 'avgCyclePct', 'tone-green'],
  ['최고 사이클 수익률', 'bestCyclePct', 'tone-green'],
  ['최저 사이클 수익률', 'worstCyclePct', 'tone-green'],
  ['최대 자금 비중', 'maxInvestPct', ''],
];

export default function PositionPanel({ data }) {
  return (
    <Panel
      title="자산 현황 (종목별)"
      subtitle="TQQQ"
      headerActions={
        <div className="panel-chip">
          <Star size={14} fill="currentColor" strokeWidth={1.8} />
          <span>{data.symbol}</span>
          <ChevronRight size={14} strokeWidth={2.2} />
        </div>
      }
      className="position-panel"
    >
      <div className="position-hero">
        <div className="position-main">
          <div className="symbol-name">TQQQ</div>
          <div className="position-label">현재 수익</div>
          <div className="position-profit tone-green">{data.currentProfit}</div>
          <div className="position-profit-sub tone-green">{data.currentProfitPct}</div>
        </div>

        <div className="position-side">
          {METRICS.map(([label, key]) => (
            <div key={label} className="key-value-row">
              <span>{label}</span>
              <strong>{data[key]}</strong>
            </div>
          ))}
        </div>

        <div className="position-levels">
          {LEVELS.map((level) => (
            <div key={level.label} className="level-card">
              <span className="level-label">{level.label}</span>
              <strong className={level.tone}>{data[level.key]}</strong>
              <small>{level.noteKey ? data[level.noteKey] : ''}</small>
            </div>
          ))}
        </div>
      </div>

      <div className="position-grid">
        <div>
          <div className="subheading">종목별 집계</div>
          <div className="stat-stack">
            {STATS.slice(0, 5).map(([label, key]) => (
              <div key={label} className="stat-row">
                <span>{label}</span>
                <strong>{data[key]}</strong>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="subheading">&nbsp;</div>
          <div className="stat-stack">
            {STATS.slice(5).map(([label, key]) => (
              <div key={label} className="stat-row">
                <span>{label}</span>
                <strong>{data[key]}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}
