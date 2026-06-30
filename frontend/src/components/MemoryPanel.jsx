import { useState, useEffect } from 'react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function StatChip({ label, value, color = 'text-slate-300' }) {
  return (
    <div className="flex flex-col items-center bg-slate-800 rounded-lg px-3 py-2">
      <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
      <span className="text-xs text-slate-500 mt-0.5">{label}</span>
    </div>
  );
}

function WinBar({ label, wins, total, avgPnl }) {
  const rate = total > 0 ? Math.round((wins / total) * 100) : 0;
  const barColor = rate >= 60 ? '#22c55e' : rate >= 45 ? '#f59e0b' : '#ef4444';
  return (
    <div className="space-y-0.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400 truncate max-w-[160px]">{label}</span>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`font-mono font-bold ${avgPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {avgPnl >= 0 ? '+' : ''}{avgPnl?.toFixed(2) ?? '—'}
          </span>
          <span className="text-slate-500">{total}t</span>
          <span className="font-mono text-slate-300 w-8 text-right">{rate}%</span>
        </div>
      </div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${rate}%`, backgroundColor: barColor }} />
      </div>
    </div>
  );
}

export default function MemoryPanel() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('overview');

  useEffect(() => {
    let cancelled = false;
    async function fetchMemory() {
      try {
        const res = await fetch(`${API_BASE}/api/memory`);
        if (!res.ok) throw new Error('fetch failed');
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch {
        // Neo4j may not be available — keep null silently
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchMemory();
    const interval = setInterval(fetchMemory, 60_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  const summary = data?.summary;
  const available = summary?.available;

  return (
    <div className="bg-slate-900 rounded-xl border border-slate-800 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${available ? 'bg-purple-400 animate-pulse' : 'bg-slate-600'}`} />
          <h2 className="text-slate-200 font-semibold text-sm tracking-wide">Memory Graph</h2>
        </div>
        {available && (
          <div className="flex gap-1">
            {['overview', 'signals', 'regimes', 'timing'].map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`text-xs px-2 py-0.5 rounded transition-colors ${
                  tab === t ? 'bg-purple-600 text-white' : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        )}
      </div>

      {loading && (
        <p className="text-slate-600 text-xs py-2">Loading memory graph...</p>
      )}

      {!loading && !available && (
        <div className="text-xs text-slate-600 py-2 space-y-1">
          <p>Neo4j not connected — long-term memory disabled.</p>
          <p className="text-slate-700">Start with <code className="text-slate-500">docker-compose up</code> to enable.</p>
        </div>
      )}

      {!loading && available && (
        <>
          {/* Overview tab */}
          {tab === 'overview' && (
            <div className="space-y-3">
              <div className="grid grid-cols-4 gap-2">
                <StatChip label="Resolved" value={summary.resolved ?? 0} />
                <StatChip
                  label="Win Rate"
                  value={`${summary.win_rate ?? 0}%`}
                  color={summary.win_rate >= 55 ? 'text-green-400' : summary.win_rate >= 45 ? 'text-yellow-400' : 'text-red-400'}
                />
                <StatChip
                  label="Total P&L"
                  value={`$${(summary.total_pnl ?? 0).toFixed(0)}`}
                  color={(summary.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}
                />
                <StatChip label="Signals" value={summary.unique_signals ?? 0} color="text-purple-400" />
              </div>
              <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-800">
                <span>{summary.pending ?? 0} pending decisions</span>
                <span>{summary.co_occurrence_edges ?? 0} co-occurrence edges</span>
              </div>

              {/* Anti-patterns */}
              {data?.anti_patterns?.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 mb-1.5 font-medium">Anti-patterns to avoid</p>
                  <div className="space-y-1">
                    {data.anti_patterns.slice(0, 3).map((a, i) => (
                      <div key={i} className="flex items-start gap-2 text-xs">
                        <span className="text-red-400 shrink-0">⚠</span>
                        <span className="text-slate-400">
                          <span className="text-slate-300">{a.signal}</span> in {a.regime}/{a.confluence}:{' '}
                          lost {a.loss_count}× (avg ${a.avg_loss?.toFixed(2)})
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(summary.resolved ?? 0) === 0 && (
                <p className="text-slate-600 text-xs">No resolved decisions yet. Patterns accumulate as trades close.</p>
              )}
            </div>
          )}

          {/* Signals tab */}
          {tab === 'signals' && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500 mb-2">Best signal combinations (co-occurrence graph)</p>
              {data?.best_signal_combos?.length > 0 ? (
                data.best_signal_combos.slice(0, 6).map((c, i) => (
                  <WinBar
                    key={i}
                    label={`${c.sig1} + ${c.sig2}`}
                    wins={c.wins}
                    total={c.total}
                    avgPnl={c.avg_pnl}
                  />
                ))
              ) : (
                <p className="text-slate-600 text-xs">Insufficient data — need 2+ trades per combo.</p>
              )}
            </div>
          )}

          {/* Regimes tab */}
          {tab === 'regimes' && (
            <div className="space-y-2">
              <p className="text-xs text-slate-500 mb-2">Performance by market regime</p>
              {data?.regime_performance?.length > 0 ? (
                data.regime_performance.map((r, i) => (
                  <WinBar
                    key={i}
                    label={`${r.regime} / ${r.action}`}
                    wins={r.wins}
                    total={r.total}
                    avgPnl={r.avg_pnl}
                  />
                ))
              ) : (
                <p className="text-slate-600 text-xs">No resolved trades by regime yet.</p>
              )}
              {data?.confluence_performance?.length > 0 && (
                <>
                  <p className="text-xs text-slate-500 mt-3 mb-1.5 font-medium">By MTF confluence</p>
                  {data.confluence_performance.map((c, i) => (
                    <WinBar key={i} label={c.confluence} wins={c.wins} total={c.total} avgPnl={c.avg_pnl} />
                  ))}
                </>
              )}
            </div>
          )}

          {/* Timing tab */}
          {tab === 'timing' && (
            <div className="space-y-1">
              <p className="text-xs text-slate-500 mb-2">Performance by UTC hour</p>
              {data?.time_performance?.length > 0 ? (
                <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                  {data.time_performance
                    .filter(t => t.total > 0)
                    .sort((a, b) => {
                      const ra = a.total > 0 ? a.wins / a.total : 0;
                      const rb = b.total > 0 ? b.wins / b.total : 0;
                      return rb - ra;
                    })
                    .map((t, i) => {
                      const rate = t.total > 0 ? Math.round((t.wins / t.total) * 100) : 0;
                      return (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-slate-500">{String(t.hour).padStart(2, '0')}:00 UTC</span>
                          <span className="text-slate-400">{t.session?.replace('_', ' ')}</span>
                          <span className={`font-mono ${rate >= 60 ? 'text-green-400' : rate >= 45 ? 'text-yellow-400' : 'text-red-400'}`}>
                            {rate}%
                          </span>
                        </div>
                      );
                    })}
                </div>
              ) : (
                <p className="text-slate-600 text-xs">No timing data yet.</p>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
