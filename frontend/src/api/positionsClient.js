import { buildApiUrl } from './dashboardClient.js';

async function apiCall(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(buildApiUrl(path), {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        ...(options.headers || {}),
      },
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `API error: ${response.status}`);
    }
    return response.status === 204 ? null : await response.json();
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function fetchPositions() {
  return apiCall('/api/positions');
}

export function createPosition(data) {
  return apiCall('/api/positions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updatePosition(id, data) {
  return apiCall(`/api/positions/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export function deletePosition(id) {
  return apiCall(`/api/positions/${id}`, { method: 'DELETE' });
}

export function fetchStrategies() {
  return apiCall('/api/strategies');
}
