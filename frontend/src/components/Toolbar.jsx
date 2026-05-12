import React, { useEffect, useState } from 'react';
import { AlertOctagon, Pause, Play, RefreshCw, ShieldCheck, X, Zap } from 'lucide-react';

const ICONS = {
  play: Play,
  pause: Pause,
  refresh: RefreshCw,
  spark: Zap,
  x: X,
};

const ACTION_LABELS = {
  start: '시작',
  pause: '일시정지',
  'run-once': '1회 실행',
  refresh: '새로고침',
  close: '종료',
  'kill-switch': '비상 정지',
  'kill-switch-reset': '비상 정지 해제',
};

const TEXT = {
  title: 'MMK AUTO TRAINING DASHBOARD',
  mode: '모드',
  market: '시장',
  symbolCount: '운용 심볼',
  status: '상태',
  killSwitchActive: '비상정지',
  busy: '처리 중',
};

function formatClock(value) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())} ${pad(value.getHours())}:${pad(value.getMinutes())}:${pad(value.getSeconds())}`;
}

function formatMode(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'mock') return 'Mock';
  if (normalized === 'paper' || normalized === 'paper-trading') return '모의투자';
  if (normalized === 'real' || normalized === 'live') return '실거래';
  return value || 'Mock';
}

function formatMarket(value) {
  const raw = String(value || '').trim();
  const normalized = raw.toLowerCase();
  if (normalized.includes('regular') || raw.includes('정규')) return '정규장';
  if (normalized.includes('pre') || raw.includes('프리')) return '프리마켓';
  if (normalized.includes('after') || raw.includes('애프터')) return '애프터마켓';
  if (normalized.includes('closed') || normalized.includes('close') || raw.includes('휴장')) return '휴장';
  return raw || '-';
}

function formatStatus(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'running') return '실행중';
  if (normalized === 'waiting' || normalized === 'idle') return '대기';
  if (normalized === 'stopped' || normalized === 'stop') return '정지';
  if (normalized === 'error') return '오류';
  return value || '대기';
}

function getSymbolCount(data) {
  if (Array.isArray(data?.symbols)) return data.symbols.length;
  if (Array.isArray(data?.assets)) return data.assets.length;
  return data?.symbol || data?.position?.symbol ? 1 : 0;
}

export default function Toolbar({ data, onAction, busyAction = null }) {
  const buttonsDisabled = Boolean(busyAction);
  const [clock, setClock] = useState(() => formatClock(new Date()));
  const status = data.status || 'WAITING';
  const killSwitch = data.killSwitch || { active: false };

  const systemItems = [
    [TEXT.mode, formatMode(data.mode)],
    [TEXT.market, formatMarket(data.marketStatus)],
    [TEXT.symbolCount, `${getSymbolCount(data)}개`],
    [TEXT.status, formatStatus(status)],
    ...(killSwitch.active ? [[TEXT.killSwitchActive, '활성']] : []),
  ];

  useEffect(() => {
    const timerId = globalThis.setInterval(() => setClock(formatClock(new Date())), 1000);
    return () => globalThis.clearInterval(timerId);
  }, []);

  function handleKillSwitch() {
    if (killSwitch.active) {
      onAction?.('kill-switch-reset');
    } else if (globalThis.confirm('비상 정지를 활성화하면 모든 자동매매 주문이 차단됩니다.\n계속하시겠습니까?')) {
      onAction?.('kill-switch');
    }
  }

  return (
    <header className={`dashboard-header${killSwitch.active ? ' kill-switch-active' : ''}`}>
      <div className="dashboard-title-row">
        <div className="dashboard-title">
          <h1>{TEXT.title}</h1>
        </div>
        <time className="dashboard-clock" dateTime={clock}>{clock}</time>
      </div>

      {killSwitch.active && (
        <div className="kill-switch-banner">
          <AlertOctagon size={14} />
          <span>비상 정지 활성 {killSwitch.reason ? `— ${killSwitch.reason}` : ''}</span>
        </div>
      )}

      <div className="dashboard-control-row">
        <div className="header-pill-group" aria-label="실행 상태">
          {systemItems.map(([label, value]) => (
            <div
              className={`header-pill${label === TEXT.killSwitchActive ? ' header-pill-danger' : ''}`}
              key={label}
            >
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>

        <div className="toolbar-actions">
          <div className={`toolbar-status ${status === 'RUNNING' ? 'is-running' : ''}`} aria-label={`자동매매 상태 ${status}`}>
            <span className="toolbar-status-dot" />
          </div>
          {(data.topActions || []).map((action) => {
            const Icon = ICONS[action.icon] || Play;
            const isBusy = busyAction === action.key;
            return (
              <button
                key={action.key}
                className={`toolbar-button ${action.variant} ${isBusy ? 'busy' : ''}`}
                type="button"
                aria-label={isBusy ? TEXT.busy : ACTION_LABELS[action.key] || action.label}
                title={isBusy ? TEXT.busy : ACTION_LABELS[action.key] || action.label}
                disabled={buttonsDisabled}
                onClick={() => onAction?.(action.key)}
              >
                <Icon size={15} strokeWidth={2.2} className={isBusy ? 'spin-icon' : ''} />
              </button>
            );
          })}

          <div className="toolbar-divider" />

          <button
            type="button"
            className={`toolbar-button toolbar-button-ks ${killSwitch.active ? 'ks-on' : 'ks-off'}`}
            title={killSwitch.active ? ACTION_LABELS['kill-switch-reset'] : ACTION_LABELS['kill-switch']}
            aria-label={killSwitch.active ? ACTION_LABELS['kill-switch-reset'] : ACTION_LABELS['kill-switch']}
            disabled={busyAction === 'kill-switch' || busyAction === 'kill-switch-reset'}
            onClick={handleKillSwitch}
          >
            {killSwitch.active
              ? <ShieldCheck size={13} strokeWidth={2.2} />
              : <AlertOctagon size={13} strokeWidth={2.2} />}
          </button>
        </div>
      </div>
    </header>
  );
}
