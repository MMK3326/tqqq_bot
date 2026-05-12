import { buildApiUrl } from './dashboardClient.js';

async function apiFetch(path) {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(buildApiUrl(path), {
      signal: controller.signal,
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return await response.json();
  } catch {
    return [];
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function fetchOrders({ limit = 100, positionId = null } = {}) {
  const params = new URLSearchParams({ limit });
  if (positionId != null) params.set('position_id', positionId);
  return apiFetch(`/api/orders?${params}`);
}

export function fetchSignals({ limit = 100, positionId = null } = {}) {
  const params = new URLSearchParams({ limit });
  if (positionId != null) params.set('position_id', positionId);
  return apiFetch(`/api/signals?${params}`);
}

export function fetchEquity({ limit = 200 } = {}) {
  return apiFetch(`/api/equity?limit=${limit}`);
}
