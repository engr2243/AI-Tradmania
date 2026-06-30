import { useEffect, useRef, useState } from 'react';
import { fmt } from '../utils/format';

const ACTION_STYLES = {
  BUY:  'bg-green-500/20 text-green-400 border border-green-500/30',
  SELL: 'bg-red-500/20 text-red-400 border border-red-500/30',
  HOLD: 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30',
};
const RISK_STYLES = { LOW: 'text-green-400', MEDIUM: 'text-yellow-400', HIGH: 'text-red-400' };

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

function ReasoningSteps({ reasoning }) {
  const [open, setOpen] = useState(false);
  if (!reasoning || Object.keys(reasoning).length === 0) return null;
  const LABELS = {
    step1_regime: '① Regime',
    step2_trend: '② Trend',
    step3_signals: '③ Signals',
    step4_timing: '④ Timing',
    step5_rr: '⑤ R:R',
    step6_sentiment: '⑥ Sentiment',
    step7_decision: '⑦ Decision',
  };
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(o => !o)} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
        <span>{open ? '▾' : '▸'}</span> Chain-of-Thought reasoning
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {Object.entries(LABELS).map(([key, label]) =>
            reasoning[key] ? (
              <div key={key} className="text-xs bg-slate-800/80 rounded px-2 py-1">
                <span className="text-slate-500 font-medium">{label}: </span>
                <span className="text-slate-300">{reasoning[key]}</span>
              </div>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}

export default function AIDecisions({ decision, lastUpdate, cycle, decisionMemory = [] }) {
  const historyRef = useRef([]);

  useEffect(() => {
    if (!decision?.action) return;
    const entry = { ...decision, cycle, ts: Date.now() };
    historyRef.current = [entry, ...historyRef.current].slice(0, 8);
  }, [decision, cycle]);

  const history = historyRef.current;
  const current = history[0];

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-slate-200 font-semibold text-sm tracking-wide">AI Decisions</h2>
        <span className="text-xs text-slate-500">{lastUpdate ? fmt.ago(lastUpdate) : 'waiting...'}</span>
      </div>

      {/* Current decision */}
      <div className="px-4 py-3 border-b border-slate-800">
        {current ? (
          <>
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <span className={`px-2.5 py-0.5 rounded text-xs font-bold ${ACTION_STYLES[current.action]}`}>
                {current.action}
              </span>
              {current.amount_pct > 0 && (
                <span className="text-xs text-slate-400">{current.amount_pct.toFixed(0)}% capital</span>
              )}
              {current.rr_ratio != null && (
                <span className={`text-xs font-mono font-semibold ${current.rr_ratio >= 1.5 ? 'text-green-400' : 'text-red-400'}`}>
                  R:R {current.rr_ratio.toFixed(2)}x
                </span>
              )}
              <span className={`ml-auto text-xs font-medium ${RISK_STYLES[current.risk_level] || 'text-slate-400'}`}>
                {current.risk_level}
              </span>
            </div>
            <ConfidenceBar value={current.confidence} />
            <p className="text-xs text-slate-300 mt-2 leading-relaxed">{current.reason}</p>
            {current.key_signals?.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-2">
                {current.key_signals.map((s, i) => (
                  <span key={i} className="px-1.5 py-0.5 bg-slate-800 text-slate-400 text-xs rounded">{s}</span>
                ))}
              </div>
            )}
            {(current.target_price || current.stop_loss) && (
              <div className="flex gap-4 mt-2 text-xs">
                {current.target_price && <span className="text-green-400">Target: {fmt.price(current.target_price)}</span>}
                {current.stop_loss && <span className="text-red-400">Stop: {fmt.price(current.stop_loss)}</span>}
              </div>
            )}
            <ReasoningSteps reasoning={current.reasoning} />
            {current.latency_s && (
              <p className="text-xs text-slate-600 mt-1">
                {current.provider ? `${current.provider} · ` : ''}{current.latency_s}s
              </p>
            )}
            {current.error && (
              <div className="mt-2 text-xs text-red-400 bg-red-500/10 rounded px-2 py-1">
                AI provider error — check API key in .env ({current.provider || 'unknown'})
              </div>
            )}
          </>
        ) : (
          <div className="text-slate-500 text-xs py-2">Waiting for first analysis...</div>
        )}
      </div>

      {/* Session decision memory */}
      <div className="flex-1 overflow-y-auto">
        {decisionMemory.length > 0 && (
          <div className="px-3 py-2 border-b border-slate-800/50">
            <p className="text-xs text-slate-500 mb-1">Session Memory</p>
            {[...decisionMemory].reverse().slice(0, 6).map((d, i) => {
              const icon = { profit: '✓', loss: '✗', pending: '⏳', avoided_loss: '~' }[d.outcome] || '?';
              const iconColor = { profit: 'text-green-400', loss: 'text-red-400', pending: 'text-yellow-400', avoided_loss: 'text-blue-400' }[d.outcome] || 'text-slate-400';
              return (
                <div key={i} className="flex items-center gap-2 py-1 text-xs border-b border-slate-800/30 last:border-0">
                  <span className={`${iconColor} w-3`}>{icon}</span>
                  <span className={`font-bold w-8 ${ACTION_STYLES[d.action]?.includes('green') ? 'text-green-400' : d.action === 'SELL' ? 'text-red-400' : 'text-yellow-400'}`}>{d.action}</span>
                  <span className="text-slate-500">@${(d.price_at || 0).toLocaleString()}</span>
                  {d.pnl != null && (
                    <span className={d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}>{fmt.pnl(d.pnl)}</span>
                  )}
                  <span className="text-slate-600 ml-auto">{d.confidence ? `${(d.confidence * 100).toFixed(0)}%` : ''}</span>
                </div>
              );
            })}
          </div>
        )}

        {history.slice(1).map((d, i) => (
          <div key={i} className="px-4 py-2 border-b border-slate-800/50 flex items-center gap-2">
            <span className={`px-1.5 py-0.5 rounded text-xs font-bold ${ACTION_STYLES[d.action]}`}>{d.action}</span>
            <span className="text-xs text-slate-500 flex-1 truncate">{d.reason}</span>
            <span className="text-xs text-slate-600 shrink-0">{new Date(d.ts).toLocaleTimeString('en-US', { hour12: false })}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
