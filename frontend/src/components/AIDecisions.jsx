import { useEffect, useRef } from 'react';
import { fmt } from '../utils/format';

const ACTION_STYLES = {
  BUY: 'bg-green-500/20 text-green-400 border border-green-500/30',
  SELL: 'bg-red-500/20 text-red-400 border border-red-500/30',
  HOLD: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
};

const RISK_STYLES = {
  LOW: 'text-green-400',
  MEDIUM: 'text-yellow-400',
  HIGH: 'text-red-400',
};

function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 75 ? '#22c55e' : pct >= 55 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-xs text-slate-400 w-8 text-right">{pct}%</span>
    </div>
  );
}

export default function AIDecisions({ decision, lastUpdate, cycle }) {
  const prevDecisionsRef = useRef([]);

  useEffect(() => {
    if (!decision?.action) return;
    const entry = { ...decision, cycle, ts: Date.now() };
    prevDecisionsRef.current = [entry, ...prevDecisionsRef.current].slice(0, 8);
  }, [decision, cycle]);

  const history = prevDecisionsRef.current;
  const current = history[0];

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">AI Decisions</h2>
        <span className="text-xs text-slate-500">
          {lastUpdate ? fmt.ago(lastUpdate) : 'waiting...'}
        </span>
      </div>

      {/* Current decision */}
      <div className="px-4 py-3 border-b border-slate-800">
        {current ? (
          <>
            <div className="flex items-center gap-2 mb-2">
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${ACTION_STYLES[current.action]}`}>
                {current.action}
              </span>
              {current.amount_pct > 0 && (
                <span className="text-xs text-slate-400">{current.amount_pct.toFixed(0)}% of capital</span>
              )}
              <span className={`ml-auto text-xs font-medium ${RISK_STYLES[current.risk_level] || 'text-slate-400'}`}>
                {current.risk_level} RISK
              </span>
            </div>
            <ConfidenceBar value={current.confidence} />
            <p className="text-xs text-slate-300 mt-2 leading-relaxed">{current.reason}</p>
            {current.key_signals?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {current.key_signals.map((s, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-slate-800 text-slate-400 text-xs rounded">
                    {s}
                  </span>
                ))}
              </div>
            )}
            {(current.target_price || current.stop_loss) && (
              <div className="flex gap-4 mt-2 text-xs">
                {current.target_price && (
                  <span className="text-green-400">Target: {fmt.price(current.target_price)}</span>
                )}
                {current.stop_loss && (
                  <span className="text-red-400">Stop: {fmt.price(current.stop_loss)}</span>
                )}
              </div>
            )}
            {current.error && (
              <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded px-2 py-1">
                API Error — Check ANTHROPIC_API_KEY
              </div>
            )}
          </>
        ) : (
          <div className="text-slate-500 text-xs py-2">Waiting for first analysis...</div>
        )}
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto">
        {history.slice(1).map((d, i) => (
          <div key={i} className="px-4 py-2 border-b border-slate-800/50 flex items-center gap-2">
            <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${ACTION_STYLES[d.action]}`}>
              {d.action}
            </span>
            <span className="text-xs text-slate-500 flex-1 truncate">{d.reason}</span>
            <span className="text-xs text-slate-600 shrink-0">
              {new Date(d.ts).toLocaleTimeString('en-US', { hour12: false })}
            </span>
          </div>
        ))}
        {history.length === 0 && (
          <div className="px-4 py-6 text-center text-slate-600 text-xs">No history yet</div>
        )}
      </div>
    </div>
  );
}
