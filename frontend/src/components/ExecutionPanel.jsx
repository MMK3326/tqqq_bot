import React from 'react';

const fallbackStatus = {
  phase: 'idle',
  phaseLabel: '대기',
  isRunning: false,
  isBusy: false,
  lastError: '',
  nextRunText: '대기',
  source: 'yfinance + mock_broker',
};

const phaseTone = {
  price_lookup: 'running',
  strategy: 'running',
  order: 'success',
  waiting: 'waiting',
  idle: 'idle',
  error: 'error',
  stopped: 'error',
};

function engineLabel(status) {
  if (status === 'RUNNING') return 'RUNNING';
  if (status === 'STOPPED') return 'STOPPED';
  return 'WAITING';
}

export default function ExecutionPanel({ data }) {
  const status = { ...fallbackStatus, ...(data?.executionStatus || {}) };
  const tone = phaseTone[status.phase] || 'idle';
  const errorText = status.lastError || '정상';

  return (
    <section className={`execution-panel ${tone}`}>
      <div className={`execution-phase ${tone}`}>
        <span className="execution-dot" />
        <strong>{engineLabel(data?.status)}</strong>
      </div>
      <div className="execution-ticker">
        <span>실행 단계</span>
        <strong>{status.phaseLabel}</strong>
      </div>
      <div className="execution-ticker">
        <span>다음 실행</span>
        <strong>{status.nextRunText}</strong>
      </div>
      <div className="execution-ticker">
        <span>시장</span>
        <strong>{data?.marketStatus || '-'}</strong>
      </div>
      <div className="execution-ticker">
        <span>모드</span>
        <strong>{data?.mode || '-'}</strong>
      </div>
      <div className="execution-ticker">
        <span>전략 주기</span>
        <strong>{data?.refreshSec ? `${data.refreshSec}초` : '-'}</strong>
      </div>
      <div className="execution-ticker wide">
        <span>데이터 소스</span>
        <strong>{status.source}</strong>
      </div>
      <div className={`execution-ticker wide ${status.lastError ? 'has-error' : ''}`}>
        <span>오류</span>
        <strong>{errorText}</strong>
      </div>
    </section>
  );
}
