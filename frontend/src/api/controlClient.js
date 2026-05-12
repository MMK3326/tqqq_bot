import fallbackDashboardData from '../mockData.js';
import { buildApiUrl, normalizeDashboardData } from './dashboardClient.js';

async function postRaw(path, timeoutMs = 2500) {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(buildApiUrl(path), {
      method: 'POST',
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error(`Control API failed: ${response.status}`);
    const payload = await response.json();
    return {
      ok: Boolean(payload.ok),
      action: payload.action,
      message: payload.message || '처리 완료',
      dashboard: normalizeDashboardData(payload.dashboard || fallbackDashboardData),
      source: 'api',
      error: null,
    };
  } catch (error) {
    return {
      ok: false,
      action: path,
      message: `API 서버 없음 (${path})`,
      dashboard: fallbackDashboardData,
      source: 'mock',
      error,
    };
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

async function postControlAction(action, timeoutMs = 2500) {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(buildApiUrl(`/api/control/${action}`), {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Control API failed: ${response.status}`);
    }

    const payload = await response.json();
    const dashboard = normalizeDashboardData(payload.dashboard || fallbackDashboardData);
    return {
      ok: Boolean(payload.ok),
      action: payload.action || action,
      message: payload.message || '처리 완료',
      dashboard,
      source: 'api',
      error: null,
    };
  } catch (error) {
    return {
      ok: false,
      action,
      message: `API 서버 없음: mock fallback 유지 (${action})`,
      dashboard: fallbackDashboardData,
      source: 'mock',
      error,
    };
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function controlStart() {
  return postControlAction('start');
}

export function controlPause() {
  return postControlAction('pause');
}

export function controlRunOnce() {
  return postControlAction('run-once');
}

export function controlRefresh() {
  return postControlAction('refresh');
}

export function controlClose() {
  return postControlAction('close');
}

export function controlKillSwitch(reason = '사용자 수동 비상 정지') {
  return postRaw(`/api/control/kill-switch?reason=${encodeURIComponent(reason)}`);
}

export function controlKillSwitchReset() {
  return postRaw('/api/control/kill-switch/reset');
}
