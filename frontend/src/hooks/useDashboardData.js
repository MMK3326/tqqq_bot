import { useEffect, useState } from 'react';
import fallbackDashboardData from '../mockData.js';
import { fetchDashboardData, normalizeDashboardData } from '../api/dashboardClient.js';

const DASHBOARD_POLL_SEC = 1;

function getDashboardPollMs(data) {
  const seconds = Number(data?.dashboardRefreshSec ?? DASHBOARD_POLL_SEC);
  if (!Number.isFinite(seconds) || seconds <= 0) return DASHBOARD_POLL_SEC * 1000;
  return seconds * 1000;
}

function formatLocalMessage(message) {
  const time = new Date().toTimeString().slice(0, 8);
  return `${time}  ${message}`;
}

export function useDashboardData() {
  const [state, setState] = useState({
    data: fallbackDashboardData,
    source: 'mock',
    error: null,
    isLoading: true,
  });

  useEffect(() => {
    let cancelled = false;
    let timerId = null;

    const load = async () => {
      const result = await fetchDashboardData();
      if (cancelled) return;

      setState((current) => ({
        ...current,
        data: normalizeDashboardData(result.data),
        source: result.source,
        error: result.error,
        isLoading: false,
      }));

      const nextDelayMs = getDashboardPollMs(result.data);
      timerId = globalThis.setTimeout(load, nextDelayMs);
    };

    load();

    return () => {
      cancelled = true;
      if (timerId !== null) {
        globalThis.clearTimeout(timerId);
      }
    };
  }, []);

  const refreshDashboard = async () => {
    const result = await fetchDashboardData();
    setState((current) => ({
      ...current,
      data: normalizeDashboardData(result.data),
      source: result.source,
      error: result.error,
      isLoading: false,
    }));
    return result;
  };

  const applyControlResult = (result) => {
    const normalized = normalizeDashboardData(result.dashboard);
    const nextMessages = result.message
      ? [formatLocalMessage(result.message), ...normalized.messages].slice(0, 40)
      : normalized.messages;

    setState((current) => ({
      ...current,
      data: {
        ...normalized,
        messages: nextMessages,
      },
      source: result.source,
      error: result.error,
      isLoading: false,
    }));
  };

  return {
    ...state,
    refreshDashboard,
    applyControlResult,
  };
}
