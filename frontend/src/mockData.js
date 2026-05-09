import dashboardData from './data/dashboard.mock.json';

const executionStatus = {
  phase: 'idle',
  phaseLabel: '대기',
  isRunning: false,
  isBusy: false,
  lastStartedAt: '-',
  lastFinishedAt: '-',
  lastPriceCheckAt: '-',
  lastPrice: '$73.08',
  lastSignal: 'HOLD',
  lastOrderAction: '-',
  lastOrderText: 'mock order 없음',
  lastError: '',
  nextRunText: '대기',
  source: 'mockData fallback',
  ...(dashboardData.executionStatus || {}),
};

const normalizedDashboardData = {
  ...dashboardData,
  strategyRunSec: dashboardData.strategyRunSec ?? dashboardData.refreshSec ?? 60,
  priceRefreshSec: dashboardData.priceRefreshSec ?? 60,
  dashboardRefreshSec: dashboardData.dashboardRefreshSec ?? 1,
  executionStatus,
};

export { normalizedDashboardData as dashboardData };
export default normalizedDashboardData;
