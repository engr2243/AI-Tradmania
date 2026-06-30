function Gauge({ label, value, min = 0, max = 100, zones }) {
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min)) * 100));
  let color = '#94a3b8';
  if (zones) {
    for (const z of zones) {
      if (value >= z.from && value <= z.to) { color = z.color; break; }
    }
  }
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-500">{label}</span>
        <span className="font-mono" style={{ color }}>{value?.toFixed(1) ?? '--'}</span>
      </div>
      <div className="h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function Badge({ label, value, positive }) {
  const isPositive = positive !== undefined ? positive : value === 'bullish' || value === true || value > 0;
  return (
    <div className="bg-slate-800/60 rounded-lg px-3 py-2">
      <p className="text-slate-500 text-xs mb-0.5">{label}</p>
      <p className={`text-sm font-semibold capitalize ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
        {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : String(value ?? '--')}
      </p>
    </div>
  );
}

export default function Indicators({ indicators }) {
  if (!indicators || Object.keys(indicators).length === 0) {
    return (
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide mb-3">Technical Indicators</h2>
        <p className="text-slate-600 text-xs">Waiting for OHLCV data...</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <h2 className="text-slate-200 font-semibold text-sm tracking-wide mb-3">Technical Indicators</h2>

      <div className="space-y-3 mb-4">
        <Gauge
          label="RSI (14)"
          value={indicators.rsi_14}
          min={0} max={100}
          zones={[
            { from: 0, to: 30, color: '#22c55e' },
            { from: 30, to: 70, color: '#f59e0b' },
            { from: 70, to: 100, color: '#ef4444' },
          ]}
        />
        <Gauge
          label="BB %B"
          value={indicators.bb_pct != null ? indicators.bb_pct * 100 : null}
          min={0} max={100}
          zones={[
            { from: 0, to: 20, color: '#22c55e' },
            { from: 20, to: 80, color: '#f59e0b' },
            { from: 80, to: 100, color: '#ef4444' },
          ]}
        />
        <Gauge
          label="Volume Ratio"
          value={indicators.volume_ratio}
          min={0} max={3}
          zones={[
            { from: 0, to: 0.5, color: '#94a3b8' },
            { from: 0.5, to: 1.5, color: '#f59e0b' },
            { from: 1.5, to: 3, color: '#22c55e' },
          ]}
        />
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Badge label="MACD" value={indicators.macd_trend} />
        <Badge label="EMA Trend" value={indicators.ema_trend} />
        <Badge label="BB Squeeze" value={indicators.bb_squeeze} positive={false} />
        <div className="bg-slate-800/60 rounded-lg px-3 py-2">
          <p className="text-slate-500 text-xs mb-0.5">Momentum 5-bar</p>
          <p className={`text-sm font-mono font-semibold ${indicators.momentum_5 >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {indicators.momentum_5?.toFixed(2) ?? '--'}%
          </p>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-400">
        <div>
          <p className="text-slate-600">EMA9</p>
          <p className="font-mono">${indicators.ema_9?.toFixed(0) ?? '--'}</p>
        </div>
        <div>
          <p className="text-slate-600">EMA21</p>
          <p className="font-mono">${indicators.ema_21?.toFixed(0) ?? '--'}</p>
        </div>
        <div>
          <p className="text-slate-600">ATR14</p>
          <p className="font-mono">{indicators.atr_14?.toFixed(1) ?? '--'}</p>
        </div>
      </div>
    </div>
  );
}
