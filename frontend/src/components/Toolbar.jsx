import React, { useEffect, useState } from 'react';
import { Pause, Play, RefreshCw, X, Zap } from 'lucide-react';

const ICONS = {
  play: Play,
  pause: Pause,
  refresh: RefreshCw,
  spark: Zap,
  x: X,
};

const ACTION_LABELS = {
  start: '\uc2dc\uc791',
  pause: '\uc77c\uc2dc\uc815\uc9c0',
  'run-once': '1\ud68c \uc2e4\ud589',
  refresh: '\uc0c8\ub85c\uace0\uce68',
  close: '\uc885\ub8cc',
};

const TEXT = {
  title: 'MMK AUTO TRAINING DASHBOARD',
  mode: '\ubaa8\ub4dc',
  market: '\uc2dc\uc7a5',
  symbolCount: '\uc6b4\uc6a9 \uc2ec\ubcfc',
  status: '\uc0c1\ud0dc',
  busy: '\ucc98\ub9ac \uc911',
};

function formatClock(value) {
  const pad = (number) => String(number).padStart(2, '0');
  const year = value.getFullYear();
  const month = pad(value.getMonth() + 1);
  const day = pad(value.getDate());
  const hours = pad(value.getHours());
  const minutes = pad(value.getMinutes());
  const seconds = pad(value.getSeconds());
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

function formatMode(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'mock') return 'Mock';
  if (normalized === 'paper' || normalized === 'paper-trading') return '\ubaa8\uc758\ud22c\uc790';
  if (normalized === 'real' || normalized === 'live') return '\uc2e4\uac70\ub798';
  if (normalized === 'backtest' || normalized === 'backtesting') return '\ubc31\ud14c\uc2a4\ud2b8';
  return value || 'Mock';
}

function formatMarket(value) {
  const raw = String(value || '').trim();
  const normalized = raw.toLowerCase();
  if (normalized.includes('regular') || raw.includes('\uc815\uaddc')) return '\uc815\uaddc\uc7a5';
  if (normalized.includes('pre') || raw.includes('\ud504\ub9ac')) return '\ud504\ub9ac\ub9c8\ucf13';
  if (normalized.includes('after') || raw.includes('\uc560\ud504\ud130')) return '\uc560\ud504\ud130\ub9c8\ucf13';
  if (normalized.includes('closed') || normalized.includes('close') || raw.includes('\ud734\uc7a5')) return '\ud734\uc7a5';
  return raw || '-';
}

function formatStatus(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'running') return '\uc2e4\ud589\uc911';
  if (normalized === 'waiting' || normalized === 'idle') return '\ub300\uae30';
  if (normalized === 'stopped' || normalized === 'stop') return '\uc815\uc9c0';
  if (normalized === 'error') return '\uc624\ub958';
  return value || '\ub300\uae30';
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
  const systemItems = [
    [TEXT.mode, formatMode(data.mode)],
    [TEXT.market, formatMarket(data.marketStatus)],
    [TEXT.symbolCount, `${getSymbolCount(data)}\uac1c`],
    [TEXT.status, formatStatus(status)],
  ];

  useEffect(() => {
    const timerId = globalThis.setInterval(() => {
      setClock(formatClock(new Date()));
    }, 1000);

    return () => globalThis.clearInterval(timerId);
  }, []);

  return (
    <header className="dashboard-header">
      <div className="dashboard-title-row">
        <div className="dashboard-title">
          <h1>{TEXT.title}</h1>
        </div>
        <time className="dashboard-clock" dateTime={clock}>{clock}</time>
      </div>

      <div className="dashboard-control-row">
        <div className="header-pill-group" aria-label="\uc2e4\ud589 \uc0c1\ud0dc">
          {systemItems.map(([label, value]) => (
            <div className="header-pill" key={label}>
              <span>{label}</span>
              <strong>{value}</strong>
            </div>
          ))}
        </div>

        <div className="toolbar-actions">
          <div className={`toolbar-status ${status === 'RUNNING' ? 'is-running' : ''}`} aria-label={`자동매매 상태 ${status}`}>
            <span className="toolbar-status-dot" />
          </div>
          {data.topActions.map((action) => {
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
        </div>
      </div>
    </header>
  );
}
