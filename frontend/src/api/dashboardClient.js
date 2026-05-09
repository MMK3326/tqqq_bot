import fallbackDashboardData from '../mockData.js';

const DEFAULT_TIMEOUT_MS = 2500;

export function buildApiUrl(path = '/api/dashboard') {
  const baseUrl = import.meta.env.VITE_API_BASE_URL?.trim();
  if (!baseUrl) return `http://127.0.0.1:8008${path.startsWith('/') ? path : `/${path}`}`;
  return `${baseUrl.replace(/\/$/, '')}${path.startsWith('/') ? path : `/${path}`}`;
}

export function normalizeDashboardData(raw) {
  if (!raw || typeof raw !== 'object') {
    return fallbackDashboardData;
  }

  return {
    ...fallbackDashboardData,
    ...raw,
    summaryCards: Array.isArray(raw.summaryCards) ? raw.summaryCards : fallbackDashboardData.summaryCards,
    accountRows: Array.isArray(raw.accountRows) ? raw.accountRows : fallbackDashboardData.accountRows,
    systemRows: Array.isArray(raw.systemRows) ? raw.systemRows : fallbackDashboardData.systemRows,
    messages: Array.isArray(raw.messages) ? raw.messages : fallbackDashboardData.messages,
    performanceRows: Array.isArray(raw.performanceRows) ? raw.performanceRows : fallbackDashboardData.performanceRows,
    tradeTabs: Array.isArray(raw.tradeTabs) ? raw.tradeTabs : fallbackDashboardData.tradeTabs,
    trades: Array.isArray(raw.trades) ? raw.trades : fallbackDashboardData.trades,
    topActions: Array.isArray(raw.topActions) ? raw.topActions : fallbackDashboardData.topActions,
    position: {
      ...fallbackDashboardData.position,
      ...(raw.position || {}),
    },
    executionStatus: {
      ...fallbackDashboardData.executionStatus,
      ...(raw.executionStatus || {}),
    },
  };
}

export async function fetchDashboardData({ timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(buildApiUrl(), {
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Dashboard API failed: ${response.status}`);
    }

    const data = await response.json();
    return {
      data: normalizeDashboardData(data),
      source: 'api',
      error: null,
    };
  } catch (error) {
    return {
      data: fallbackDashboardData,
      source: 'mock',
      error,
    };
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}
