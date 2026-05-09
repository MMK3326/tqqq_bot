export function isEmptyValue(value) {
  return value === null || value === undefined || value === '' || Number.isNaN(value);
}

export function safeDisplay(value) {
  return isEmptyValue(value) ? '-' : String(value);
}

export function toNumber(value) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value !== 'string') return null;
  const normalized = value.replace(/[$,%+,\s]/g, '');
  if (!normalized || normalized === '-') return null;
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value, digits = 2) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  return numeric.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatCurrency(value) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  return `$${Math.abs(numeric).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatSignedCurrency(value) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : '';
  return `${sign}$${Math.abs(numeric).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPercent(value) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  return `${numeric.toFixed(2)}%`;
}

export function formatSignedPercent(value) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : '';
  return `${sign}${Math.abs(numeric).toFixed(2)}%`;
}

export function formatQuantity(value) {
  const numeric = toNumber(value);
  if (numeric === null) return safeDisplay(value);
  if (numeric === 0) return '0';
  return numeric.toFixed(6);
}

export function formatUnit(value) {
  const numeric = toNumber(value);
  if (numeric !== null) return `${numeric} Unit`;
  const matched = String(value || '').match(/-?\d+(\.\d+)?/);
  if (matched) return `${matched[0]} Unit`;
  return safeDisplay(value);
}

export function getValueClass(value) {
  const numeric = toNumber(value);
  if (numeric === null || numeric === 0) return '';
  return numeric > 0 ? 'tone-green' : 'tone-red';
}

export function getStatusClass(status) {
  const value = String(status || '').toLowerCase();
  if (value === '\ubcf4\uc720\uc911' || value === 'holding' || value === '\uc815\uc0c1') return 'state-holding';
  if (value === '\uc775\uc808 \ub300\uae30' || value === 'take_profit_wait') return 'state-warning';
  if (value === '\ucd94\uac00\ub9e4\uc218 \ub300\uae30' || value === 'buy_wait') return 'state-buy';
  if (value === '\uc5d0\ub7ec' || value === 'error' || value === '\uc624\ub958') return 'state-error';
  return 'state-waiting';
}

export const statusClass = getStatusClass;
export const valueTone = getValueClass;
export const formatPrice = formatCurrency;
export const formatMoney = formatSignedCurrency;

function pctNumber(value) {
  return toNumber(value);
}

function moneyNumber(value) {
  return toNumber(value);
}

function roundedUnit(value) {
  if (value === null || !Number.isFinite(value)) return null;
  return Math.round(value * 100) / 100;
}

function deriveInvestedUnit({ investedUnit, quantity, unitShares, investedAmount, adjustedUnitAmount, stage }) {
  const explicitUnit = toNumber(investedUnit);
  if (explicitUnit !== null && explicitUnit > 0) return explicitUnit;

  const numericQuantity = toNumber(quantity);
  const numericUnitShares = toNumber(unitShares);
  if (numericQuantity !== null && numericQuantity > 0 && numericUnitShares !== null && numericUnitShares > 0) {
    return roundedUnit(numericQuantity / numericUnitShares);
  }

  const numericInvested = toNumber(investedAmount);
  const numericAdjustedUnit = toNumber(adjustedUnitAmount);
  if (numericInvested !== null && numericInvested > 0 && numericAdjustedUnit !== null && numericAdjustedUnit > 0) {
    return roundedUnit(numericInvested / numericAdjustedUnit);
  }

  const stageUnit = toNumber(stage);
  if (stageUnit !== null) return stageUnit;
  return null;
}

export function buildSymbolRows(data) {
  const sourceRows = Array.isArray(data?.symbols) ? data.symbols : Array.isArray(data?.assets) ? data.assets : null;
  if (sourceRows) {
    return sourceRows.map((row) => normalizeSymbolRow(row));
  }

  const position = data?.position || {};
  const symbol = position.symbol || data?.symbol;
  if (!symbol) return [];

  const quantity = moneyNumber(position.quantity);
  const returnRate = pctNumber(position.currentProfitPct);
  const unrealizedPnl = moneyNumber(position.currentProfit);
  const allocation = pctNumber(position.investedPct);
  const nextBuyRate = pctNumber(position.nextBuyNote);
  const nextTakeProfitRate = pctNumber(position.nextTakeProfitNote);
  const holding = quantity !== null && quantity > 0;
  const unitShares = moneyNumber(position.unitShares);
  const adjustedUnitAmount = moneyNumber(position.adjustedUnitAmount);
  const investedUnit = deriveInvestedUnit({
    investedUnit: position.investedUnit,
    quantity,
    unitShares,
    investedAmount: position.investedAmount,
    adjustedUnitAmount,
    stage: position.currentStep,
  });

  return [
    {
      symbol,
      name: position.name || position.description || `${symbol} \uc790\ub3d9\ub9e4\ub9e4 \ub300\uc0c1`,
      description: position.description || position.name || `${symbol} \uc790\ub3d9\ub9e4\ub9e4 \ub300\uc0c1`,
      status: holding ? '\ubcf4\uc720\uc911' : '\ub300\uae30',
      currentPrice: moneyNumber(position.currentPrice),
      returnRate,
      unrealizedPnl,
      allocation,
      stage: position.currentStep || '-',
      investedUnit,
      initialEntryPrice: moneyNumber(position.firstPrice),
      firstPrice: moneyNumber(position.firstPrice),
      rawUnitAmount: moneyNumber(position.rawUnitAmount),
      adjustedUnitAmount,
      unitShares,
      nextBuyPrice: moneyNumber(position.nextBuyPrice),
      nextBuyRate,
      nextTakeProfitPrice: moneyNumber(position.nextTakeProfitPrice),
      nextTakeProfitRate,
      quantity,
      avgPrice: moneyNumber(position.avgPrice),
      investedAmount: moneyNumber(position.investedAmount),
      strategyStatus: data?.executionStatus?.phaseLabel || (holding ? '\uc815\uc0c1' : '\ub300\uae30'),
      strategySummary: `${data?.mode || 'mock'} \ubaa8\ub4dc \u00b7 \ubd84\ud560 \ub9e4\uc218/\uc775\uc808 \u00b7 ${data?.refreshSec || 60}\ucd08 \uc8fc\uae30`,
    },
  ];
}

export function normalizeSymbolRow(row) {
  const quantity = toNumber(row.quantity);
  const investedAmount = toNumber(row.investedAmount);
  const unitShares = toNumber(row.unitShares);
  const adjustedUnitAmount = toNumber(row.adjustedUnitAmount ?? row.adjustedUnit);
  const investedUnit = deriveInvestedUnit({
    investedUnit: row.investedUnit ?? row.unit ?? row.currentUnit,
    quantity,
    unitShares,
    investedAmount,
    adjustedUnitAmount,
    stage: row.stage,
  });

  return {
    symbol: safeDisplay(row.symbol),
    name: row.name || row.description || safeDisplay(row.symbol),
    description: row.description || row.name || safeDisplay(row.symbol),
    status: row.status || '\ub300\uae30',
    currentPrice: toNumber(row.currentPrice),
    returnRate: toNumber(row.returnRate),
    unrealizedPnl: toNumber(row.unrealizedPnl),
    allocation: toNumber(row.allocation),
    stage: row.stage || '-',
    investedUnit: investedUnit ?? row.stage ?? '-',
    initialEntryPrice: toNumber(row.initialEntryPrice ?? row.firstPrice ?? row.entryPrice),
    firstPrice: toNumber(row.firstPrice ?? row.initialEntryPrice ?? row.entryPrice),
    rawUnitAmount: toNumber(row.rawUnitAmount ?? row.rawUnit ?? row.unitAmount),
    adjustedUnitAmount,
    unitShares,
    nextBuyPrice: toNumber(row.nextBuyPrice),
    nextBuyRate: toNumber(row.nextBuyRate),
    nextTakeProfitPrice: toNumber(row.nextTakeProfitPrice),
    nextTakeProfitRate: toNumber(row.nextTakeProfitRate),
    quantity,
    avgPrice: toNumber(row.avgPrice),
    investedAmount,
    strategyStatus: row.strategyStatus || row.status || '\ub300\uae30',
    strategySummary: row.strategySummary || '-',
  };
}
