export const fmt = {
  price: (v, decimals = 2) =>
    v != null ? `$${Number(v).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}` : '--',

  pct: (v, decimals = 2) =>
    v != null ? `${v >= 0 ? '+' : ''}${Number(v).toFixed(decimals)}%` : '--',

  pnl: (v) => {
    if (v == null) return '--';
    const s = v >= 0 ? '+' : '';
    return `${s}$${Math.abs(v).toFixed(2)}`;
  },

  qty: (v, decimals = 6) =>
    v != null ? Number(v).toFixed(decimals) : '--',

  ts: (ms) => {
    if (!ms) return '--';
    return new Date(ms).toLocaleTimeString('en-US', { hour12: false });
  },

  ago: (date) => {
    if (!date) return 'never';
    const s = Math.floor((Date.now() - date.getTime()) / 1000);
    if (s < 60) return `${s}s ago`;
    return `${Math.floor(s / 60)}m ago`;
  },
};
