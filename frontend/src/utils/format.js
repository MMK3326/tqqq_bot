export function formatMoney(value) {
  const number = Number(value || 0);
  return `$${number.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatSignedMoney(value) {
  const number = Number(value || 0);
  if (number > 0) return `+${formatMoney(number)}`;
  if (number < 0) return `-${formatMoney(Math.abs(number))}`;
  return '$0.00';
}

export function formatPct(value) {
  const number = Number(value || 0);
  const sign = number > 0 ? '+' : '';
  return `${sign}${number.toFixed(2)}%`;
}

export function formatQuantity(value) {
  const number = Number(value || 0);
  return number.toLocaleString('en-US', {
    minimumFractionDigits: 6,
    maximumFractionDigits: 6,
  });
}

export function toneClass(tone) {
  if (tone === 'green') return 'tone-green';
  if (tone === 'yellow') return 'tone-yellow';
  if (tone === 'red') return 'tone-red';
  if (tone === 'blue') return 'tone-blue';
  return 'tone-neutral';
}
